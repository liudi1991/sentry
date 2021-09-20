import * as React from 'react';

import {Team} from 'app/types';
import getDisplayName from 'app/utils/getDisplayName';
import useTeams from 'app/utils/useTeams';

type InjectedTeamsProps = {
  teams?: Team[];
};

/**
 * Higher order component that provides a list of teams
 */
const withTeams = <P extends InjectedTeamsProps>(
  WrappedComponent: React.ComponentType<P>
) => {
  const WithTeams: React.FC<Omit<P, keyof InjectedTeamsProps> & InjectedTeamsProps> =
    props => {
      const {teams} = useTeams();
      return <WrappedComponent teams={teams} {...(props as P)} />;
    };

  WithTeams.displayName = `withTeams(${getDisplayName(WrappedComponent)})`;

  return WithTeams;
};

export default withTeams;
