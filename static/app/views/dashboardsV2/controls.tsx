import * as React from 'react';
import styled from '@emotion/styled';

import Feature from 'app/components/acl/feature';
import FeatureDisabled from 'app/components/acl/featureDisabled';
import Button from 'app/components/button';
import ButtonBar from 'app/components/buttonBar';
import Confirm from 'app/components/confirm';
import Hovercard from 'app/components/hovercard';
import {IconAdd, IconEdit} from 'app/icons';
import {t} from 'app/locale';
import space from 'app/styles/space';
import {Organization} from 'app/types';

import {DashboardListItem, DashboardState} from './types';

type Props = {
  organization: Organization;
  dashboards: DashboardListItem[];
  onEdit: () => void;
  onCancel: () => void;
  onCommit: () => void;
  onDelete: () => void;
  onAddWidget: () => void;
  onAddIssueWidget: () => void;
  dashboardState: DashboardState;
};

class Controls extends React.Component<Props> {
  render() {
    const {
      organization,
      dashboardState,
      dashboards,
      onEdit,
      onCancel,
      onCommit,
      onDelete,
      onAddWidget,
      onAddIssueWidget,
    } = this.props;

    const cancelButton = (
      <Button
        data-test-id="dashboard-cancel"
        onClick={e => {
          e.preventDefault();
          onCancel();
        }}
      >
        {t('Cancel')}
      </Button>
    );

    if ([DashboardState.EDIT, DashboardState.PENDING_DELETE].includes(dashboardState)) {
      return (
        <StyledButtonBar gap={1} key="edit-controls">
          {cancelButton}
          <Confirm
            priority="danger"
            message={t('Are you sure you want to delete this dashboard?')}
            onConfirm={onDelete}
            disabled={dashboards.length <= 1}
          >
            <Button data-test-id="dashboard-delete" priority="danger">
              {t('Delete')}
            </Button>
          </Confirm>
          <Button
            data-test-id="dashboard-commit"
            onClick={e => {
              e.preventDefault();
              onCommit();
            }}
            priority="primary"
          >
            {t('Save and Finish')}
          </Button>
        </StyledButtonBar>
      );
    }

    if (dashboardState === 'create') {
      return (
        <StyledButtonBar gap={1} key="create-controls">
          {cancelButton}
          <Button
            data-test-id="dashboard-commit"
            onClick={e => {
              e.preventDefault();
              onCommit();
            }}
            priority="primary"
          >
            {t('Save and Finish')}
          </Button>
        </StyledButtonBar>
      );
    }

    return (
      <StyledButtonBar gap={1} key="controls">
        <DashboardEditFeature>
          {hasFeature => (
            <React.Fragment>
              <Button
                data-test-id="dashboard-edit"
                onClick={e => {
                  e.preventDefault();
                  onEdit();
                }}
                icon={<IconEdit size="xs" />}
                disabled={!hasFeature}
                priority={
                  organization.features.includes('widget-library') ? 'default' : 'primary'
                }
              >
                {t('Edit Dashboard')}
              </Button>
              {organization.features.includes('widget-library') ? (
                <Button
                  data-test-id="add-widget-library"
                  priority="primary"
                  icon={<IconAdd isCircled size="s" />}
                  onClick={e => {
                    e.preventDefault();
                    onAddWidget();
                  }}
                >
                  {t('Add Widget')}
                </Button>
              ) : null}
              {organization.features.includes('issues-in-dashboards') ? (
                <Button
                  data-test-id="dashboard-add-issues-widget"
                  priority="primary"
                  icon={<IconAdd isCircled size="s" />}
                  onClick={e => {
                    e.preventDefault();
                    onAddIssueWidget();
                  }}
                  disabled={!hasFeature}
                >
                  {t('Add Issue Widget')}
                </Button>
              ) : null}
            </React.Fragment>
          )}
        </DashboardEditFeature>
      </StyledButtonBar>
    );
  }
}

const DashboardEditFeature = ({
  children,
}: {
  children: (hasFeature: boolean) => React.ReactNode;
}) => {
  const noFeatureMessage = t('Requires dashboard editing.');

  const renderDisabled = p => (
    <Hovercard
      body={
        <FeatureDisabled
          features={p.features}
          hideHelpToggle
          message={noFeatureMessage}
          featureName={noFeatureMessage}
        />
      }
    >
      {p.children(p)}
    </Hovercard>
  );

  return (
    <Feature
      hookName="feature-disabled:dashboards-edit"
      features={['organizations:dashboards-edit']}
      renderDisabled={renderDisabled}
    >
      {({hasFeature}) => children(hasFeature)}
    </Feature>
  );
};

const StyledButtonBar = styled(ButtonBar)`
  @media (max-width: ${p => p.theme.breakpoints[0]}) {
    grid-auto-flow: row;
    grid-row-gap: ${space(1)};
    width: 100%;
  }
`;

export default Controls;
