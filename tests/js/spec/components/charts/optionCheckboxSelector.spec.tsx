import {mountWithTheme} from 'sentry-test/enzyme';
import {initializeOrg} from 'sentry-test/initializeOrg';

import OptionCheckboxSelector from 'app/components/charts/optionCheckboxSelector';
import {t} from 'app/locale';

describe('EventsV2 > OptionCheckboxSelector', function () {
  const features = ['discover-basic'];
  const yAxisValue = ['count()', 'failure_count()'];
  const yAxisOptions = [
    {label: 'count()', value: 'count()'},
    {label: 'failure_count()', value: 'failure_count()'},
    {label: 'count_unique(user)', value: 'count_unique(user)'},
  ];
  let organization, initialData, selected, wrapper, onChangeStub, dropdownItem;

  beforeEach(() => {
    // @ts-expect-error
    organization = TestStubs.Organization({
      features: [...features, 'connect-discover-and-dashboards'],
    });

    // Start off with an invalid view (empty is invalid)
    initialData = initializeOrg({
      organization,
      router: {
        location: {query: {query: 'tag:value'}},
      },
      project: 1,
      projects: [],
    });
    selected = [...yAxisValue];
    wrapper = mountWithTheme(
      <OptionCheckboxSelector
        title={t('Y-Axis')}
        selected={selected}
        options={yAxisOptions}
        onChange={() => undefined}
      />,
      initialData.routerContext
    );
    // Parent component usually handles the new selected state but we don't have one in this test so we update props ourselves
    onChangeStub = jest.fn(newSelected => wrapper.setProps({selected: newSelected}));
    wrapper.setProps({onChange: onChangeStub});

    dropdownItem = wrapper.find('StyledDropdownItem');
  });

  it('renders yAxisOptions with yAxisValue selected', async function () {
    expect(dropdownItem.at(0).find('span').last().children().html()).toEqual('count()');
    expect(dropdownItem.at(1).find('span').last().children().html()).toEqual(
      'failure_count()'
    );
    expect(dropdownItem.at(2).find('span').last().children().html()).toEqual(
      'count_unique(user)'
    );
    expect(dropdownItem.at(0).props().isChecked).toEqual(true);
    expect(dropdownItem.at(1).props().isChecked).toEqual(true);
    expect(dropdownItem.at(2).props().isChecked).toEqual(false);
  });

  it('calls onChange prop with new checkbox option state', async function () {
    dropdownItem.at(0).find('span').first().simulate('click');
    expect(onChangeStub).toHaveBeenCalledWith(['failure_count()']);
    dropdownItem.at(0).find('span').first().simulate('click');
    expect(onChangeStub).toHaveBeenCalledWith(['failure_count()', 'count()']);
    dropdownItem.at(1).find('span').first().simulate('click');
    expect(onChangeStub).toHaveBeenCalledWith(['count()']);
    dropdownItem.at(1).find('span').first().simulate('click');
    expect(onChangeStub).toHaveBeenCalledWith(['count()', 'failure_count()']);
    dropdownItem.at(2).find('span').first().simulate('click');
    expect(onChangeStub).toHaveBeenCalledWith([
      'count()',
      'failure_count()',
      'count_unique(user)',
    ]);
  });

  it('does not uncheck options when clicked if only one option is currently selected', async function () {
    dropdownItem.at(0).find('span').first().simulate('click');
    expect(onChangeStub).toHaveBeenCalledWith(['failure_count()']);
    dropdownItem.at(1).find('span').first().simulate('click');
    expect(onChangeStub).toHaveBeenCalledWith(['failure_count()']);
  });
});
