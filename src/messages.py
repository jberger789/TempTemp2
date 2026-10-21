from datetime import date, time

def format_message(message_type: str, auth_code: str|None = None, **kwargs) -> str:
    return f"{message_type}|{auth_code or ''}|{format_params(**kwargs) or ''}"

def format_params(**kwargs):
    if not kwargs:
        return None
    else:
        return ';'.join([format_single_param(k,kwargs[k]) for k in kwargs.keys()])

def format_single_param(name: str, val: int | float | str | date | time | list | dict) -> str:
    """
    Creates a string with the appropriate format for a single parameter
    as well as for nested dictionaries (which become multiple parameters)
    """
    if isinstance(val, int):
        return f"{name}_I_{str(val)}"
    elif isinstance(val, float):
        return f"{name}_F_{str(val)}"
    elif isinstance(val, str):
        return f"{name}_S_{val}"
    elif isinstance(val, date):
        return f"{name}_D_{val.strftime('%Y-%m-%d')}"
    elif isinstance(val, time):
        return f"{name}_T_{val.strftime('%H:%M')}"
    elif isinstance(val, list):
        return f"{name}_{format_list(val)}"
    elif isinstance(val, dict):
        # Check if it is a nested dictionary
        if isinstance(next(iter(val.values()),None), dict):
            return format_nested_dict(val)
        else:
            return  f"{name}_{format_dict(val)}"
    else:
        raise(TypeError(f"'{name}' has invalid parameter type '{type(val)}'"))
    
def format_nested_dict(d: dict[dict]) -> str:
    l = []
    for outer in d.keys():
        for inner in d[outer].keys():
            l.append(format_single_param(name = f"{outer}/{inner}", val = d[outer][inner]))
    return ';'.join(l)

def format_list(l: list) -> str:
    # Check if the list is empty
    if len(l)==0:
        return "LS_()"
    else:
        rs = "L"
        if isinstance(l[0], int):
            rs += "I_"
        elif isinstance(l[0], float):
            rs += "F_"
        elif isinstance(l[0], str):
            rs += "S_"
        else:
            raise(TypeError(f"First value '{l[0]}' has invalid parameter type '{type(l[0])}'"))
        rs += '('+',,'.join([str(v) for v in l])+')'
        return rs

def format_dict(d: dict) -> str:
    rs = "MS_" # In practice, the only non-nested dicts we work with have string values so we don't need to check the type
    rs += '('+',,'.join([f"{k}->{d[k]}" for k in d.keys()])+')'
    return rs


def unformat_message(formatted_str: str) -> tuple[str, str|None, dict|None]:
    '''Returns a ValueError if not in correct format'''
    message_type,auth_code,ps = [x.strip() for x in formatted_str.strip().split('|')]
    if auth_code == '':
        auth_code = None
    if ps != '':
        params = unpack_param_str(ps)
    else:
        params = None

    return message_type, auth_code, params

TYPE_CASTS = {'I': int, 'F': float, 'S': str, 'D': date.fromisoformat, 'T': time.fromisoformat}

def unpack_param_str(param_str: str) -> dict:
    outer = inner = None # To prevent old values from causing issues in certain malformed inputs

    params = {}
    plist = param_str.split(";")
    for p in plist:
        name, ptype, val = [x.strip() for x in p.split('_')] # Strip trailing and leading whitespaces, done in several places
        if ptype in TYPE_CASTS:
            if "/" in name:
                outer,inner = [x.strip() for x in name.split('/')]
                if "NestedData" not in params:
                    params["NestedData"] = {}
                if outer not in params["NestedData"]:
                    params["NestedData"][outer] = {}
                params["NestedData"][outer][inner] = TYPE_CASTS[ptype](val)
            else:
                params[name] = TYPE_CASTS[ptype](val)
        elif len(ptype) == 2:
            vlist = [x.strip() for x in val.strip('()').split(',,')]
            if ptype[0] == "L":
                if ptype[1] in TYPE_CASTS:
                    if len(vlist) > 0 and vlist[0] != "":
                        params[name] = [TYPE_CASTS[ptype[1]](v) for v in vlist]
                    else:
                        params[name] = []
            elif ptype[0] == "M":
                if ptype[1] in TYPE_CASTS:
                    d = {}
                    if len(vlist) > 0 and vlist[0] != "":
                        for v in vlist:
                            dk,dv = [x.strip() for x in v.split('->')]
                            d[dk] = TYPE_CASTS[ptype[1]](dv)
                    params[name] = d
        if name not in params:
            if "/" not in name or "NestedData" not in params or outer not in params["NestedData"] or inner not in params["NestedData"][outer]:
                raise ValueError(f"Parameter '{name}' has invalid parameter type code '{ptype}'")
        
    return params