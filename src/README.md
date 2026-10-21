# Implementation

> Replace this file with instructions for **your** implementation.
>
> Your partner group has to run this in Phase 4 without asking you anything and without reading your source. Write it for them. Remember that while the network protocol you are implementing should be the same, your application interfaces can be wildly different -- one team might expect commands to be entered as text in a terminal style client while another team might assume command line arguments are provided for each request. That is fine!

## Requirements

<!-- e.g. Python 3.10+, no third-party packages -->
Should probably work on Python 3.10+, tested on Python 3.14.8

## Running the server

```sh
python3 src/server.py --port 9000
```

## Running the client

```sh
python3 src/client.py --host <server ip> --port 9000
```

## Example session
<!-- Paste a short transcript: what you typed, what came back. -->
Type queries as they appear in spec v2 -  
`"Message Type" | "Auth Code" (optional) | "Parameter Name"_"Parameter type"_"Parameter value"`  
with a ";" between Parameters.

Responses will be printed as the raw response message, and a (slightly) more legibly
formatted response.  
You do **not** need to include all parameters when the spec provides a default value.
For example:

`Locations Request ||` (ask for all locations), is successfully responded with
```
Raw Response: Locations Response||LocationDictionary_MS_(BOS->Boston,,NYC->New York,,TKY->Tokyo,,SGP->Singapore,,LAX->Los Angeles,,DET->Detroit)
Message Type: Locations Response
Message Parameters: {'LocationDictionary': {'BOS': 'Boston', 'NYC': 'New York', 'TKY': 'Tokyo', 'SGP': 'Singapore', 'LAX': 'Los Angeles', 'DET': 'Detroit'}}
```
And using a more formal `Locations Request || Limit_I_2` (ask for the first 2 locations)
is responded with
```
Raw Response: Locations Response||LocationDictionary_MS_(BOS->Boston,,NYC->New York)
Message Type: Locations Response
Message Parameters: {'LocationDictionary': {'BOS': 'Boston', 'NYC': 'New York'}}
```
We can get the forecast data now that we have locations.
```
> Forecast Request || Location_S_BOS;ConditionNames_LS_(Temp,,Desc,,PChance); AdditionalDays_I_2
Raw Response: Forecast Response||Location_S_BOS;0/Desc_S_Storms;0/PChance_F_41.0;0/Temp_F_60.3;1/Desc_S_Sunny;1/PChance_F_78.03;1/Temp_F_53.6;2/Desc_S_Cloudy;2/PChance_F_20.61;2/Temp_F_60.9
Message Type: Forecast Response
Message Parameters: {'Location': 'BOS', 'NestedData': {'0': {'Desc': 'Storms', 'PChance': 41.0, 'Temp': 60.3}, '1': {'Desc': 'Sunny', 'PChance': 78.03, 'Temp': 53.6}, '2': {'Desc': 'Cloudy', 'PChance': 20.61, 'Temp': 60.9}}}
```
Telling us on day 0 (today) it'll be stormy, with a 41% rain chance and temperature of
60.3 degrees F.

We predefine 3 passwords to try: `password123`,`XKCD`, and `123!/x`.  
Using an incorrect password to try and get an auth code:  
```
> Auth Request||     Password_S_ABCD
Raw Response: Error Message||ErrorCode_S_NEED AUTH;Message_S_Incorrect password
Message Type: Error Message
Message Parameters: {'ErrorCode': 'NEED AUTH', 'Message': 'Incorrect password'}
```
Using a correct password:
```
> Auth Request||                          Password_S_XKCD
Raw Response: Auth Response||Code_S_89Np32;ExpiryTime_I_1792549718
Message Type: Auth Response
Message Parameters: {'Code': '89Np32', 'ExpiryTime': 1792549718}
```
We can then use that auth code (will not be the same for a user) to edit forecast
information.
```
> Edit Forecast Data Request|89Np32|Location_S_BOS; Date_D_2026-10-20;Temp_F_58;Desc_S_Sunny;PChance_I_99
Raw Response: Edit Forecast Data Response||Location_S_BOS;Old/Desc_S_Storms;Old/PChance_F_41.0;Old/Temp_F_60.3;New/Desc_S_Sunny;New/PChance_F_99.0;New/Temp_F_58.0
Message Type: Edit Forecast Data Response
Message Parameters: {'Location': 'BOS', 'NestedData': {'Old': {'Desc': 'Storms', 'PChance': 41.0, 'Temp': 60.3}, 'New': {'Desc': 'Sunny', 'PChance': 99.0, 'Temp': 58.0}}}
```
Calling Forecast Request to confirm the changes shows they were successful:
```
> Forecast Request || Location_S_BOS;ConditionNames_LS_(Temp,,Desc,,PChance); AdditionalDays_I_2
Raw Response: Forecast Response||Location_S_BOS;0/Desc_S_Sunny;0/PChance_F_99.0;0/Temp_F_58.0;1/Desc_S_Sunny;1/PChance_F_78.03;1/Temp_F_53.6;2/Desc_S_Cloudy;2/PChance_F_20.61;2/Temp_F_60.9
Message Type: Forecast Response
Message Parameters: {'Location': 'BOS', 'NestedData': {'0': {'Desc': 'Sunny', 'PChance': 99.0, 'Temp': 58.0}, '1': {'Desc': 'Sunny', 'PChance': 78.03, 'Temp': 53.6}, '2': {'Desc': 'Cloudy', 'PChance': 20.61, 'Temp': 60.9}}}
```
etc. etc.
## Known limitations
<!-- Anything unfinished or deliberately out of scope. Honesty here is free marks. -->
During implementation, it became apparent that the order errors were checked in was
patently absurd. The specified ordering had parameters (An unknown location) being
evaluated before the message type was even known!  
We opted to not use this particular ordering, as it is much easier to check for
parameter mismatches *after* the higher level error possibilities have been evaluated.

We realized that although the spec was clear on what LocationCode and LocationName referred to, there was some ambiguity as to what "Location" meant (though the examples treated it the same as Location Code). In order to work around this, we wrote some code to try to correct any understandable errors related to this ambiguity - though in theory it could introduce issues in the event that there are any situations where two locations with distinct LocationCodes have the same LocationName (which would be true in real life, though not as much of a concern at the scale for this assignement), though these issues will not cause errors, they will simply provide data for a different location than desired.  In theory it should try to use the provided value as a LocationCode first, but this was not rigorously tested.

Another issue was that the examples in the spec treated PChance as an int, but elsewhere in the spec PChance was defined as a float - we made some effort to resolve the ambiguity but it was not possible to ensure that we will not have issues with the other team without having communicated with them.

Relatedly, the spec implies that the Status Response parameter AdminActive was a bool, but bools were never defined in the message format section of the spec, so we instead treated it as a string.  If we had more time we would have tried to add some error handling to this.

In general, we did not have time to rigorously test every possible type of input or error that could even be reasonably expected, so it is possible that there are many errors that we failed to catch.  FoFor example, one major edge case we did not check is what might happen if some tried to submit a multiply nested dictionary, though most likely it would just result in a format error.  We also did not have a chance to thoroughly test running the code on separate devices, different operating systems, etc.  If we had more time it would have also been nice to document the code a bit better as some parts are perhaps a bit confusing.

Additional Features we would have liked to implement:

We had discussed the possibility of both including the possibility of Celsius 
temperatures, and of time zone conversion for queries where the client is in a 
different time zone.  
While we likely could've fashioned a time zone converter using local date/time 
differences, we ran out of time to implement it.   
Celsius would have required an additional field in temperature-related requests that
was not in spec (which we ran out of time on).