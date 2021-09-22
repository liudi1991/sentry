import datetime
from typing import Optional, Set

from sentry.utils import redis

# redis key for entry storing current list of LPQ members
LPQ_MEMBERS_KEY = "store.symbolicate-event-lpq-selected"


class RealtimeMetricsStore:
    def __init__(
        self,
        cluster: redis._RedisCluster,
        counter_bucket_size: int,
        counter_ttl: datetime.timedelta,
        prefix: str = "symbolicate_event_low_priority",
    ) -> None:
        if counter_bucket_size <= 0:
            raise ValueError("bucket size must be at least 1")

        self._counter_bucket_size = counter_bucket_size
        self.inner = cluster
        self._counter_ttl: int = int(counter_ttl / datetime.timedelta(milliseconds=1))
        self._prefix = prefix

    def increment_project_event_counter(self, project_id: int, timestamp: float) -> None:
        """Increment the event counter for the given project_id.

        The key is computed from the project_id and the timestamp of the symbolication request, rounded
        down to this object's bucket size. If the key is not currently set to expire, it will be set to expire
        in ttl seconds.
        """
        timestamp = int(timestamp)
        if self._counter_bucket_size > 1:
            timestamp -= timestamp % self._counter_bucket_size

        key = f"{self._prefix}:{project_id}:{timestamp}"

        with self.inner.pipeline() as pipeline:
            pipeline.set(key, 0, nx=True, px=self._counter_ttl)
            pipeline.incr(key)
            pipeline.execute()

    # TODO: do these killswitch helpers belong here, or in a different class? LowPriorityQueueStore?
    # This probably needs locking
    def get_lpq_projects(self) -> Set[int]:
        """
        Fetches the list of projects that are currently using the low priority queue.

        Returns a list of project IDs.
        """
        return set(
            filter(
                None, {_to_int(project_id) for project_id in self.inner.smembers(LPQ_MEMBERS_KEY)}
            )
        )

    def add_project_to_lpq(self, project_id: int) -> None:
        """
        Moves projects to the low priority queue.

        This forces all symbolication events triggered by the specified projects to be redirected to
        the low priority queue, unless these projects have been manually excluded from the low
        priority queue via the store.symbolicate-event-lpq-never kill switch.

        Raises ``LowPriorityQueueMembershipError`` if this fails to add the specified project to the
        low priority queue.
        """

        added = self.inner.sadd(LPQ_MEMBERS_KEY, project_id)

        # Looks like this might already be in the LPQ, or redis failed to add it. This is only a
        # problem if redis failed to add it.
        if added == 0 and not self.inner.sismember(LPQ_MEMBERS_KEY, project_id):
            raise LowPriorityQueueMembershipError(
                f"Failed to move project ID {project_id} to the low priority queue"
            )

    def remove_projects_from_lpq(self, project_ids: Set[int]) -> Set[int]:
        """
        Removes projects from the low priority queue.

        This restores all specified projects back to the regular queue, unless they have been
        manually forced into the low priority queue via the store.symbolicate-event-lpq-always kill
        switch.


        Returns all projects that have been successfully removed from the low priority queue.
        """
        if len(project_ids) == 0:
            return set()

        removed = self.inner.srem(LPQ_MEMBERS_KEY, *project_ids)

        if removed == len(project_ids):
            return project_ids

        # Looks like only a subset of the project IDs were removed from the LPQ list.
        in_lpq = self.inner.smembers(LPQ_MEMBERS_KEY)
        was_removed = project_ids.intersection(in_lpq)

        return was_removed


def _to_int(value: str) -> Optional[int]:
    try:
        return int(value) if value else None
    except ValueError:
        return None


class LowPriorityQueueMembershipError(Exception):
    """
    Something went wrong while updating the list of projects designated for the low priority queue.
    """

    pass
