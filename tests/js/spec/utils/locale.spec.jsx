import {mountWithTheme, screen} from 'sentry-test/reactTestingLibrary';

import {tct} from 'app/locale';

describe('locale.gettextComponentTemplate', () => {
  it('should render two component templates inside the same parent', async () => {
    mountWithTheme(
      <div data-test-id="subject">
        {tct('1st: [one]', {
          one: 'one',
        })}
        {tct('2nd: [two]', {
          two: 'two',
        })}
      </div>
    );

    expect(screen.getByTestId('subject')).toHaveTextContent('1st: one2nd: two');
  });
});
