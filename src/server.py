#!/usr/bin/env python3
"""
UDP echo server — a starting point for Project 1.

This is NOT your protocol. It is the smallest thing that receives a datagram and
replies, so you have something that runs on day one. Replace handle() with your
own message parsing and response logic.

    python3 src/server.py --port 9000
"""

import argparse
import socket

import string
import random
from datetime import datetime as dt, timedelta as tdelt, date

from typing import Any
from itertools import islice

import messages # Custom file for shared functionality

ERROR_DICT = {
    "UNKNOWN LOCATION": "The requested location code is not that of a supported location.",
    "INVALID FORMAT": "The message does not follow WSP format.",
    "UNKNOWN MESSAGE": "The message type is not supported by WSP.",
    "MISSING PARAMETER": "The request does not contain a required parameter.",
    "PREEXISTING LOCATION": "The location to be added has the same code as another location.",
    "NEED AUTH": "Insufficient authorization provided for the attempted action.",
    "INVALID UNIT": "The UNIT value is not F or C.",
    "INVALID DAYS": "The requested number of forecast days is greater than 14.",
    "INVALID FIELD": "A field contains an unsupported/invalid value.",
    "MISC ERROR": "Unspecified/Unknown error."
}

CONDITIONS = {
    "Desc": ["Sunny", "Cloudy", "Overcast", "Rainy", "Storms"],
    "PType": ["None", "Rain", "Snow", "Sleet", "Hail"],
    # I dont want to bother being fancy. brute force.
    "WDir": ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW",
            "SW", "WSW", "W", "WNW", "NW", "NNW"]
}
CONDITION_TYPES = ["Desc","Humid", "PChance", 
        "PType", "Temp","UV", "WDir", "WSpeed"]

class WEP_Server():

    def __init__(self):
        # default server vars
        # Server status vars
        self.start_time = dt.now()
        self.admin_active = "False"
        #location dict
        self.locations = {
            "BOS": "Boston",
            "NYC": "New York",
            "TKY": "Tokyo",
            "SGP": "Singapore",
            "LAX": "Los Angeles",
            "DET": "Detroit"
            }
        
        # set default weather.
        self.forecasts = {
            code: self.generate_forecast() for code in self.locations
        }
        # set up codes
        self.accepted_passwords = ["password123", "XKCD", "123!/x"]
        # dict. Key = password, value = tuple of Code & ExpiryTime
        self.authcodes = {}

    def handle(self, data: bytes, addr: tuple[str, int]) -> bytes:
        """Handle one datagram and return the bytes to send back.

        Right now this echoes. Your protocol goes here: parse `data` according to
        your spec, work out which message type it is, and build a reply.

        For this project you may assume the network is reliable -- every datagram arrives
        exactly once, in order -- so you do not need duplicate detection or retransmission.
        What your spec does still have to answer:
        - what happens when `data` is malformed, empty, or a type you don't recognise
        - whether you reply with an error or stay silent, and what an error looks like
        - `addr` is the only thing identifying the client, and it is spoofable
        """
        response = None
        # Parse Message type
        try:
            message = data.decode("ascii")
            mtype, authcode, params = messages.unformat_message(message)
        except Exception as e:
            # Catch errors when trying to parse incoming messages
            data = self.error_response(error_code="INVALID FORMAT", message=str(e))
        else:
            # Match to an existing one or throw an error
            # Given a specific message type, go to a specific routine
            match mtype:
                case "Status Request":
                    response = self.get_status()
                case "Locations Request":
                    response = self.get_locations(params)
                case "Forecast Request":
                    response = self.get_forecasts(params)
                case "Auth Request":
                    response = self.grant_auth(params)
                case "Append Forecast Data Request":
                    response = self.append_forecast(authcode, params)
                case "Edit Forecast Data Request":
                    response = self.edit_forecast(authcode, params)
                case "Append Location Data Request":
                    response = self.add_location(authcode, params)
                case _:
                    response = self.error_response("UNKNOWN MESSAGE")

            data = response
        
        print(f"  <- {len(data)} bytes from {addr[0]}:{addr[1]}: {data!r}", flush=True)
        return data.encode()

    def get_status(self) -> str:
        """Provide the server's status.
        Curren local date and time,
        If an Admin is active,
        & Uptime.
        """

        return messages.format_message(
            message_type="Status Response",
            CurTime = dt.now().time(),
            LocalDate = date.today(),
            AdminActive = self.admin_active,
            Uptime = (dt.now() - self.start_time).total_seconds()
        )

    def get_locations(self, params: dict[Any]|None) -> str:
        """Provide the location dictionary.
        Convert it into a string matching format specification.
        """
        if params is not None and "Limit" in params and params["Limit"] != -1:
            limit = params["Limit"]
            if not isinstance(limit,int):
                return self.error_response(
                    error_code="INVALID FIELD", 
                    message=f"Limit must be an int, not {type(limit).__name__}"
                )

        else:
            # Otherwise use the default of all locations
            limit = len(self.locations)
        
        if limit < -1:
            return self.error_response(
                error_code="INVALID FIELD", 
                message=f"{limit} is not a valid value for the 'Limit' parameter"
            )
        
        # Truncate the returned dict based on limit
        rdict = dict(islice(self.locations.items(), limit)) 

        return messages.format_message(
            message_type="Locations Response",
            LocationDictionary=rdict
        )

    def locations_error_correction(self, loc: str) -> str:
        """Returns the appropriate location code for either a location code or location name, to ameliorate spec ambiguity"""
        
        if loc in self.locations.keys():
            return loc
        else:
            if loc in self.locations.values():
                # Set it to the location code that matches the received location
                for k,v in self.locations.items():
                    if v == loc:
                        return k 
            else:
                raise(ValueError(f"{loc} is not a valid location"))


    def get_forecasts(self, params: dict[Any]) -> str:
        """Provide the forecast for a specific location up to a # of days."""

        # For maximum compatibility we allow some leeway for mixing up location names and location codes, as "Location" was not clearly defined in the spec
        if params is None or ("Location" not in params and "LocationCode" not in params and "LocationName" not in params):
            return self.error_response(
                error_code="MISSING PARAMETER",
                message="No location was provided, or the parameter name was incorrect"
            )
        else:
            loc = params.get("Location", params.get("LocationCode", params.get("LocationName")))
            try:
                location_code = self.locations_error_correction(loc)
            except Exception as e:
                return self.error_response(
                    error_code="UNKNOWN LOCATION",
                    message=str(e)
                )

        additional_days = params.get("AdditionalDays", 0)
        if not isinstance(additional_days,int):
            return self.error_response(
                error_code="INVALID FIELD",
                message=f"AdditionalDays should be of type int, not type {type(additional_days).__name__}"
            )
        
        if additional_days > 14 or additional_days < 0:
            return self.error_response(
                error_code="INVALID DAYS", 
                message=f"{additional_days} is not a valid number of days"
            )

        condition_names = params.get("ConditionNames", None)

        loc_forecasts = self.forecasts[location_code]

        response_fcs = {}

        # additional_days+1 since default is to only give today
        for day_num in range(additional_days+1):
            day = (date.today() + tdelt(days=day_num))
            # for safety
            if day not in loc_forecasts:
                continue
            # gets all conditions
            conditions = loc_forecasts[day]
            # filters
            if condition_names is not None and len(condition_names) > 0:
                conditions = {
                    name: cond
                    for name, cond in conditions.items() if name in condition_names
                }
            
            response_fcs[str(day_num)] = conditions
        
        # return result
        return messages.format_message(
            message_type = "Forecast Response",
            Location = location_code,
            NestedData = response_fcs
        )

    def grant_auth(self, params: dict[Any], duration: int = 60) -> str:
        """Check if the password matches one of an authorized user,
        then generate & store a temporary authorization code.
        Provide that & the expiry time to the user.
        """
        self.clean_auth()

        try: 
            password = params["Password"]
        except (TypeError,KeyError):
            return self.error_response(
                error_code="MISSING PARAMETER",
                message="No password was provided"
            )
        
        if password not in self.accepted_passwords:
            # Realized none of our errors really make sense if someone
            # without auth tries to get it. Closest match.
            return self.error_response(
                error_code="NEED AUTH",
                message="Incorrect password"
            )
        # Always generates, in case someone wants to refresh their authcode
        # generate an authcode
        authcode = ''.join(random.choices(string.ascii_letters+string.digits, k=6))
        # generate an expiry time, 1 hr by default
        expireTime = dt.now()+tdelt(minutes=duration)

        self.authcodes[authcode] = expireTime

        return messages.format_message(
            message_type = "Auth Response",
            Code = authcode,
            ExpiryTime = int(expireTime.timestamp())
        )

    def append_forecast(self, authcode: str|None, params: dict[Any]) -> str:
        """If user is authenticated, appends the day's conditions to the next open date
        for a location.
        """
        self.clean_auth()

        # For maximum compatibility we allow some leeway for mixing up location names and location codes, as "Location" was not clearly defined in the spec
        if params is None or ("Location" not in params and "LocationCode" not in params and "LocationName" not in params):
            return self.error_response(
                error_code="MISSING PARAMETER",
                message="No location was provided, or the parameter name was incorrect"
            )
        else:
            loc = params.get("Location", params.get("LocationCode", params.get("LocationName")))
            try:
                location_code = self.locations_error_correction(loc)
            except Exception as e:
                return self.error_response(
                    error_code="UNKNOWN LOCATION",
                    message=str(e)
                )

        conditions = {}
        for c in CONDITION_TYPES:
            if c in params:
                conditions[c]=params[c]
        if not set(CONDITION_TYPES).issubset(conditions):
            return self.error_response(
                error_code="MISSING PARAMETER",
                message="Conditions were not fully defined"
            )
        
        # Check the auth code
        if authcode is None:
            return self.error_response(
                error_code="NEED AUTH",
                message="No authorization code was provided"
            )
        elif authcode not in self.authcodes:
            return self.error_response(
                error_code="NEED AUTH",
                message="The provided authorization code is not valid"
            )
        
        # find next unset day
        loc_forecasts = self.forecasts[location_code]
        next_day = date.today()
        while next_day in loc_forecasts:
            next_day += tdelt(days=1)

        # adds forecase
        loc_forecasts[next_day] = conditions.copy()

        return messages.format_message(
            message_type = "Append Forecast Data Response",
            Location = location_code,
            Date = next_day,
            **conditions
        )


    def edit_forecast(self, authcode: str|None, params: dict[Any]) -> str:
        """Updates the forecast on a given date with those conditions."""
        self.clean_auth() # to ensure authcode is fine
        
        # For maximum compatibility we allow some leeway for mixing up location names and location codes, as "Location" was not clearly defined in the spec
        if params is None or ("Location" not in params and "LocationCode" not in params and "LocationName" not in params):
            return self.error_response(
                error_code="MISSING PARAMETER",
                message="No location was provided, or the parameter name was incorrect"
            )
        else:
            loc = params.get("Location", params.get("LocationCode", params.get("LocationName")))
            try:
                location_code = self.locations_error_correction(loc)
            except Exception as e:
                return self.error_response(
                    error_code="UNKNOWN LOCATION",
                    message=str(e)
                )
        
        # Check that the date parameter is provided as expected
        if "Date" not in params:
            return self.error_response(
                error_code="MISSING PARAMETER",
                message="No date was provided, or the parameter name was incorrect"
            )
        else:
            forec_date = params["Date"]

        # Set up the conditions requested by the user
        conditions = {}
        for c in CONDITION_TYPES:
            if c in params:
                conditions[c]=params[c]
        
        # Check if conditions is empty
        if not conditions:
            return self.error_response(
                error_code="MISSING PARAMETER",
                message="No conditions to update were provided"    
            )
        for cond in conditions:
            if cond not in CONDITION_TYPES:
                return self.error_response(
                    error_code="INVALID FIELD",
                    message=f"{cond} is not a valid condition"    
                )

        # Check the auth code
        if authcode is None:
            return self.error_response(
                error_code="NEED AUTH",
                message="No authorization code was provided"
            )
        elif authcode not in self.authcodes:
            return self.error_response(
                error_code="NEED AUTH",
                message="The provided authorization code is not valid"
            )
        
        if forec_date not in self.forecasts[location_code]:
            return self.error_response(
                error_code="INVALID FIELD",
                message=f"{forec_date} is not a valid date for the request action")

        current_forecast = self.forecasts[location_code][forec_date]

        old_conds = {}
        new_conds = {}
        for cond_name,new_cond_val in conditions.items():
            old_conds[cond_name] = old_cond_val = current_forecast[cond_name]
            #In order to account for issues where server and client might disagree on whether something is a float or an int
            try:
                new_conds[cond_name] = type(old_cond_val)(new_cond_val)
            except (TypeError,ValueError):
                return self.error_response(
                    error_code="INVALID FIELD",
                    message=f"There is an irreconcilable type mismatch.  The existing {cond_name} is of type {type(old_cond_val).__name__}, but the newly provided value is of {type(new_cond_val).__name__}"
                )
        
        current_forecast.update(new_conds)
    
        return messages.format_message(
            message_type = "Edit Forecast Data Response",
            Location = location_code,
            NestedData = {"Old": old_conds, "New": new_conds}
        )

    def add_location(self, authcode: str|None, params: dict[Any]) -> str:
        """Updates the locations dict with a new location."""
        self.clean_auth() # to ensure authcode is fine

        # Validate the auth code
        if authcode is None:
            return self.error_response(
                error_code="NEED AUTH",
                message="No authorization code was provided"
            )
        elif authcode not in self.authcodes:
            return self.error_response(
                error_code="NEED AUTH",
                message="The provided authorization code is not valid"
            )
        
        # validate the location parameters
        if params is None:
            return self.error_response(
                error_code="MISSING PARAMETER",
                message="No parameters were provided. Required parameters are LocationCode and LocationName"    
            )
        elif "LocationCode" not in params:
            return self.error_response(
                error_code="MISSING PARAMETER",
                message="No location code was provided"    
            )
        elif "LocationName" not in params:
            return self.error_response(
                error_code="MISSING PARAMETER",
                message="No location name was provided"
            )
        else: 
            loc_code = params["LocationCode"]
            loc_name = params["LocationName"]

        if not isinstance(loc_code,str):
            return self.error_response(
                error_code="INVALID FIELD",
                message=f"The location code {loc_code} should be a string, not a {type(loc_code).__name__}"
            )
        elif not isinstance(loc_name,str):
            return self.error_response(
                error_code="INVALID FIELD",
                message=f"The location name {loc_name} should be a string, not a {type(loc_name).__name__}"
            )

        # Check that the location code does not already exist
        if loc_code in self.locations:
            return self.error_response(
                error_code="PREEXISTING LOCATION",
                message=f"The location code {loc_code} already exists and thus cannot be added"
            )
        self.locations[loc_code] = loc_name
        self.forecasts[loc_code] = {}
    
        return messages.format_message(
            message_type = "Append Location Data Response"
        )

    def error_response(self, error_code: str, message: str = "") -> str:
        """Given an error code, passes back an error response with a
        useful message on what caused the error.
        """
        
        if error_code not in ERROR_DICT:
            error_code = "MISC ERROR"
        
        # Use the default message for the error type if no useful information was passed
        if message == "":
            message = ERROR_DICT[error_code]

        return messages.format_message(
            message_type = "Error Message",
            ErrorCode = error_code,
            Message = message
        )
        

    def clean_auth(self):
        """Helper Function. Removes expired authcodes."""
        now = dt.now()
        delete_keys = []
        for code, expiry in self.authcodes.items():
            if now >= expiry:
                delete_keys.append(code)

        for code in delete_keys:
            del self.authcodes[code]

    def generate_day(self) -> dict:
        """Generates random weather information for a single day. Not fancy.
        Will have weird days like 'Sunny, PChance 95%, Hail, Wind 40 MPH'.
        """
        wdict = {"Desc": None,"Humid": None, "PChance": None, 
            "PType": None, "Temp": None,"UV": None, "WDir": None,
            "WSpeed": None}
        wdict["Desc"] = random.choice(CONDITIONS["Desc"])
        wdict["Humid"] = round(random.uniform(0, 100), 2)
        wdict["PChance"] = round(random.uniform(0, 100), 2)
        wdict["PType"] = random.choice(CONDITIONS["PType"])
        # gets a random temp & clamps b/w -10 and 105 F.
        wdict["Temp"] = round(max(-10, min(105 ,random.normalvariate(65, 15))), 1)
        wdict["UV"] = round(random.uniform(1,11), 1)
        wdict["WDir"] = random.choice(CONDITIONS["WDir"])
        wdict["WSpeed"] = round(random.uniform(0, 50),5)
        
        return wdict

    def generate_forecast(self,days = 15):
        forecast = {}
        for i in range(days):
            day = date.today() + tdelt(days=i)
            forecast[day]=self.generate_day()
        return forecast

def main() -> None:
    ap = argparse.ArgumentParser(description="Project 1 UDP server")
    ap.add_argument("--host", default="0.0.0.0", help="address to bind (default: all)")
    ap.add_argument("--port", type=int, default=9000, help="port to bind (default: 9000)")
    args = ap.parse_args()

    # SOCK_DGRAM is UDP. There is no listen() and no accept() — no connections exist.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.host, args.port))

    server = WEP_Server()

    print(f"listening on {args.host}:{args.port} (ctrl-c to stop)", flush=True)

    try:
        while True:
            # Re
            # 65535 is the largest a UDP datagram can be (about 65 KB of payload).
            # A message bigger than that cannot be sent at all, so if your protocol
            # can produce one, your spec has to say what the sender does instead.
            data, addr = sock.recvfrom(65535)
            reply = server.handle(data, addr)
            if reply is not None:
                sock.sendto(reply, addr)
                print(f"  -> {len(reply)} bytes to {addr[0]}:{addr[1]}", flush=True)
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
