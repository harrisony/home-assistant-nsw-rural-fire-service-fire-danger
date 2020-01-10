# NSW Rural Fire Service/ACT Emergency Services Agency - Fire Danger

The NSW Rural Fire Service provides an [XML feed](http://www.rfs.nsw.gov.au/feeds/fdrToban.xml) that contains the fire danger
details for today and tomorrow for districts in the state as well as the ACT.

While the Australian Capital Territory is included in the NSW RFS feed, it has in the past failed to include total fire bans
declared by the ACT Emergency Services Agency (ESA). 

This fork builds upon the work of @exxamalte to return correct ACT information and makes some more opinionated changes in regards to sensors. 

## Installation

### Install custom component code
In your [configuration folder](https://www.home-assistant.io/docs/configuration/)
create subfolder `<config>/custom_components` and copy the folder
`nsw_rural_fire_service_fire_danger` into the new `custom_components` folder.


## Configuration Example


### Fire Danger Sensor

Have a look at the XML feed at http://www.rfs.nsw.gov.au/feeds/fdrToban.xml
and find your district. The district's name must be configured as 
`district_name` as shown in the following example:

```yaml
sensor:
  - platform: nsw_rural_fire_service_fire_danger
    district_name: Greater Sydney Region
```

The above configuration will generate a sensor with entity id 
`sensor.fire_danger_in_greater_sydney_region` which is further used in the
examples below.

The sensor's state will return the current fire danger level.

The following attributes will be available for use in `template` sensors.

| Attribute             | Description                                 |
|-----------------------|---------------------------------------------|
| district              | District name                               |
| region_number         | Internal number of this district            |
| councils              | List of all councils in this district       |
| danger_level_today    | Today's danger level                        |
| danger_level_tomorrow | Tomorrow's danger level                     |
| fire_ban_today        | Indicates whether there is a fire ban today |
| fire_ban_tomorrow     | Indicates whether there is a fire ban today |



### Fire Ban Today
```yaml
binary_sensor:
  - platform: template
    sensors:
      fire_ban_today:
        friendly_name: "Fire Ban Today"
        value_template: "{{ state_attr('sensor.fire_danger_in_greater_sydney_region', 'fire_ban_today') }}"
        device_class: safety
```
