from deta import Base
from os import getenv
settings_sb= Base("FormToEmailServiceSettings")

def get_env_variable(variable_name,default_value=None):
    variable=settings_sb.get(variable_name)
    if(not variable):
        settings_sb.put({"key":variable_name,"value":getenv(variable_name,default_value)})
        return getenv(variable_name,default_value)
    return variable['value']