"""Constants for the Family Safety integration."""

DOMAIN = "family_safety"
PLATFORMS = ["sensor"]

# Config entry data keys
CONF_TOKENS = "tokens"

# Update interval (seconds)
UPDATE_INTERVAL = 300  # 5 minutes

# Services
SERVICE_SET_ALLOWANCE = "set_allowance"
SERVICE_ADD_ALLOWANCE = "add_allowance"

ATTR_CHILD = "child"
ATTR_DAY = "day"
ATTR_MINUTES = "minutes"

VALID_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
