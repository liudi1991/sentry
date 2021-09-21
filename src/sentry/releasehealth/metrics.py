from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

import pytz
from snuba_sdk import BooleanCondition, Column, Condition, Entity, Op, Query
from snuba_sdk.expressions import Granularity
from snuba_sdk.query import SelectableExpression

from sentry.models.project import Project
from sentry.releasehealth.base import ReleaseHealthBackend
from sentry.sentry_metrics import indexer
from sentry.sentry_metrics.indexer.base import UseCase
from sentry.snuba.dataset import Dataset
from sentry.utils.snuba import raw_snql_query


def metric_id(org_id: int, name: str) -> int:
    index = indexer.resolve(org_id, UseCase.TAG_KEY, name)  # type: ignore
    assert index is not None  # TODO: assert too strong?
    return index  # type: ignore


def tag_key(org_id: int, name: str) -> str:
    index = indexer.resolve(org_id, UseCase.TAG_KEY, name)  # type: ignore
    assert index is not None
    return f"tags[{index}]"


def tag_value(org_id: int, name: str) -> int:
    index = indexer.resolve(org_id, UseCase.TAG_VALUE, name)  # type: ignore
    assert index is not None
    return index  # type: ignore


def reverse_tag_value(org_id: int, index: int) -> str:
    str_value = indexer.reverse_resolve(org_id, UseCase.TAG_VALUE, index)  # type: ignore
    assert str_value is not None
    return str_value  # type: ignore


class MetricsReleaseHealthBackend(ReleaseHealthBackend):
    """Gets release health results from the metrics dataset"""

    def get_current_and_previous_crash_free_rates(
        self,
        project_ids: Sequence[int],
        current_start: datetime,
        current_end: datetime,
        previous_start: datetime,
        previous_end: datetime,
        rollup: int,
        org_id: Optional[int] = None,
    ) -> ReleaseHealthBackend.CurrentAndPreviousCrashFreeRates:
        if org_id is None:
            org_id = self._get_org_id(project_ids)

        projects_crash_free_rate_dict: ReleaseHealthBackend.CurrentAndPreviousCrashFreeRates = {
            prj: {"currentCrashFreeRate": None, "previousCrashFreeRate": None}
            for prj in project_ids
        }

        previous = self._get_crash_free_rate_data(
            org_id,
            project_ids,
            previous_start,
            previous_end,
            rollup,
        )

        for project_id, project_data in previous.items():
            projects_crash_free_rate_dict[project_id][
                "previousCrashFreeRate"
            ] = self._compute_crash_free_rate(project_data)

        current = self._get_crash_free_rate_data(
            org_id,
            project_ids,
            current_start,
            current_end,
            rollup,
        )

        for project_id, project_data in current.items():
            projects_crash_free_rate_dict[project_id][
                "currentCrashFreeRate"
            ] = self._compute_crash_free_rate(project_data)

        return projects_crash_free_rate_dict

    @staticmethod
    def _get_org_id(project_ids: Sequence[int]) -> int:
        projects = Project.objects.get_many_from_cache(project_ids)
        org_ids: Set[int] = {project.organization_id for project in projects}
        if len(org_ids) != 1:
            raise ValueError("Expected projects to be from the same organization")

        return org_ids.pop()

    @staticmethod
    def _get_crash_free_rate_data(
        org_id: int,
        project_ids: Sequence[int],
        start: datetime,
        end: datetime,
        rollup: int,
    ) -> Dict[int, Dict[str, float]]:

        data: Dict[int, Dict[str, float]] = {}

        session_status = tag_key(org_id, "session.status")

        count_query = Query(
            dataset=Dataset.Metrics.value,
            match=Entity("metrics_counters"),
            select=[Column("value")],
            where=[
                Condition(Column("org_id"), Op.EQ, org_id),
                Condition(Column("project_id"), Op.IN, project_ids),
                Condition(Column("metric_id"), Op.EQ, metric_id(org_id, "session")),
                Condition(Column("timestamp"), Op.GTE, start),
                Condition(Column("timestamp"), Op.LT, end),
            ],
            groupby=[
                Column("project_id"),
                Column(session_status),
            ],
            granularity=Granularity(rollup),
        )

        count_data = raw_snql_query(
            count_query, referrer="releasehealth.metrics.get_crash_free_data", use_cache=False
        )["data"]

        for row in count_data:
            project_data = data.setdefault(row["project_id"], {})
            tag_value = reverse_tag_value(org_id, row[session_status])
            project_data[tag_value] = row["value"]

        return data

    @staticmethod
    def _compute_crash_free_rate(data: Dict[str, float]) -> Optional[float]:
        total_session_count = data.get("init", 0)
        crash_count = data.get("crashed", 0)

        if total_session_count == 0:
            return None

        crash_free_rate = 1.0 - (crash_count / total_session_count)

        # If crash count is larger than total session count for some reason
        crash_free_rate = 100 * max(0.0, crash_free_rate)

        return crash_free_rate

    def get_release_adoption(
        self,
        project_releases: Sequence[Tuple[int, str]],
        environments: Optional[Sequence[str]] = None,
        now=None,
        org_id: Optional[int] = None,
    ):
        project_ids = list({x[0] for x in project_releases})
        if org_id is None:
            org_id = self._get_org_id(project_ids)

        if now is None:
            now = datetime.now(pytz.utc)

        return self._get_release_adoption_impl(
            now, org_id, project_releases, project_ids, environments
        )

    @staticmethod
    def _get_release_adoption_impl(
        now: datetime,
        org_id: int,
        project_releases: Sequence[Tuple[int, str]],
        project_ids: Sequence[int],
        environments: Optional[Sequence[str]] = None,
    ):
        start = now - timedelta(days=1)

        def _get_common_where(total):
            where_common: List[Union[BooleanCondition, Condition]] = [
                Condition(Column("org_id"), Op.EQ, org_id),
                Condition(Column("project_id"), Op.IN, project_ids),
                Condition(Column("timestamp"), Op.GTE, start),
                Condition(Column("timestamp"), Op.LT, now),
                Condition(
                    Column(tag_key(org_id, "session.status")), Op.EQ, tag_value(org_id, "init")
                ),
            ]

            if environments is not None:
                where_common.append(
                    Condition(
                        Column(tag_key(org_id, "environment")),
                        Op.IN,
                        list(tag_value(org_id, x) for x in environments),
                    )
                )

            if not total:
                where_common.append(
                    Condition(
                        Column(tag_key(org_id, "release")),
                        Op.IN,
                        list(tag_value(org_id, x) for _, x in project_releases),
                    )
                )

            return where_common

        def _get_common_groupby(total) -> List[SelectableExpression]:
            if total:
                return [Column("project_id")]
            else:
                return [Column("project_id"), Column("release")]

        def _convert_results(data, total):
            if total:
                return {x["project_id"]: x["value"] for x in data}
            else:
                return {(x["project_id"], x["release"]): x["value"] for x in data}

        def _count_sessions(total, referrer) -> Dict[Any, int]:
            query = Query(
                dataset=Dataset.Metrics.value,
                match=Entity("metrics_counters"),
                select=[Column("value")],
                where=_get_common_where(total)
                + [
                    Condition(Column("metric_id"), Op.EQ, metric_id(org_id, "session")),
                ],
                groupby=_get_common_groupby(total),
            )

            return _convert_results(
                raw_snql_query(
                    query,
                    referrer=referrer,
                    use_cache=False,
                )["data"],
                total=total,
            )

        def _count_users(total, referrer) -> Dict[Any, int]:
            query = Query(
                dataset=Dataset.Metrics.value,
                match=Entity("metrics_sets"),
                select=[Column("value")],
                where=_get_common_where(total)
                + [
                    Condition(Column("metric_id"), Op.EQ, metric_id(org_id, "user")),
                ],
                groupby=_get_common_groupby(total),
            )

            return _convert_results(
                raw_snql_query(
                    query,
                    referrer=referrer,
                    use_cache=False,
                )["data"],
                total=total,
            )

        # XXX(markus): Four queries are quite horrible for this... the old code
        # sufficed with two. From what I understand, ClickHouse would have to
        # gain a function uniqCombined64MergeIf, i.e. a conditional variant of
        # what we already use.
        #
        # Alternatively we may want to use a threadpool here to send the
        # queries in parallel.

        # NOTE: referrers are spelled out as single static string literal so
        # S&S folks can search for it more easily. No string formatting
        # business please!

        # Count of sessions/users for given list of environments and timerange, per-project
        sessions_per_project: Dict[int, int] = _count_sessions(
            total=True, referrer="releasehealth.metrics.get_release_adoption.total_sessions"
        )
        users_per_project: Dict[int, int] = _count_users(
            total=True, referrer="releasehealth.metrics.get_release_adoption.total_users"
        )

        # Count of sessions/users for given list of environments and timerange AND GIVEN RELEASES, per-project
        sessions_per_release: Dict[Tuple[int, str], int] = _count_sessions(
            total=True, referrer="releasehealth.metrics.get_release_adoption.releases_sessions"
        )
        users_per_release: Dict[Tuple[int, str], int] = _count_users(
            total=False, referrer="releasehealth.metrics.get_release_adoption.releases_users"
        )

        rv = {}

        for project_id, release in project_releases:
            release_users = users_per_release.get((project_id, release))
            total_users = users_per_project.get(project_id)

            release_sessions = sessions_per_release.get((project_id, release))
            total_sessions = sessions_per_project.get(project_id)

            rv[project_id, release] = {
                "adoption": float(release_users) / total_users * 100
                if release_users and total_users
                else None,
                "sessions_adoption": float(release_sessions) / total_sessions * 100
                if release_sessions and total_sessions
                else None,
                "users_24h": release_users,
                "sessions_24h": release_sessions,
                "project_users_24h": total_users,
                "project_sessions_24h": total_sessions,
            }

        return rv
