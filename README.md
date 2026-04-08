# homeassistant-family-safety

A Home Assistant custom integration for **Microsoft Family Safety**, with a companion Python library (`pyfamilysafety2`) for programmatic access.

Manage your children's **Windows screen time** directly from Home Assistant — read current allowances, set limits, and add bonus time via automations.

---

## Features

- 📊 **Sensors** — Today's screen time allowance and available window for each child
- ⚙️ **Services** — Set or add to screen time allowance (for automations)
- 🔐 **Secure auth** — Microsoft device code flow (no password stored, tokens refresh automatically)
- 🔄 **Auto-refresh** — Tokens never expire as long as HA is running

---

## Installation via HACS

1. In Home Assistant, go to **HACS → Integrations → ⋮ → Custom repositories**
2. Add `https://github.com/mhenaire/homeassistant-family-safety` as an **Integration**
3. Search for "Family Safety" in HACS and install
4. Restart Home Assistant
5. Go to **Settings → Integrations → Add → Microsoft Family Safety**
6. Follow the on-screen instructions to authorize

---

## Setup

During setup, you'll be shown a code and a URL:

> Go to **https://microsoft.com/link** and enter code **XXXXXXXX**

Open that URL on any device (phone, computer), sign in with the **family organizer's** Microsoft account, and click Approve. That's it.

---

## Entities

For each child in your family, one sensor is created:

| Entity | Description |
|--------|-------------|
| `sensor.{child}_windows_screen_time_allowance` | Today's Windows allowance in minutes (0 = blocked) |

The sensor exposes the full week's schedule as attributes:

| Attribute | Description |
|-----------|-------------|
| `monday_allowance_minutes` … `sunday_allowance_minutes` | Allowance in minutes for each day |
| `monday_window_start` … `sunday_window_start` | Start of available window (HH:MM) |
| `monday_window_end` … `sunday_window_end` | End of available window (HH:MM) |

---

## Services

### `family_safety.set_allowance`

Set the screen time allowance for a child.

```yaml
service: family_safety.set_allowance
data:
  child: Felix
  day: today       # or monday, tuesday, etc.
  minutes: 60
```

### `family_safety.add_allowance`

Add (or subtract) minutes from today's allowance.

```yaml
service: family_safety.add_allowance
data:
  child: Felix
  minutes: 30      # use negative to reduce
```

---

## Example Automations

### Add 30 min when homework is done

```yaml
automation:
  - alias: "Felix homework done → bonus screen time"
    trigger:
      - platform: state
        entity_id: input_boolean.felix_homework_done
        to: "on"
    action:
      - service: family_safety.add_allowance
        data:
          child: Felix
          minutes: 30
```

### Block screen time on school nights

```yaml
automation:
  - alias: "School night screen time off"
    trigger:
      - platform: time
        at: "20:00:00"
    condition:
      - condition: time
        weekday: [mon, tue, wed, thu]
    action:
      - service: family_safety.set_allowance
        data:
          child: Felix
          day: today
          minutes: 0
```

---

## Library Usage (`pyfamilysafety2`)

```python
import asyncio
import aiohttp
from pyfamilysafety2 import FamilySafety

async def main():
    async with aiohttp.ClientSession() as session:
        # First time: device code flow
        code = await FamilySafety.start_device_auth(session)
        print(f"Go to {code.verification_uri} and enter {code.user_code}")
        fs = await FamilySafety.wait_for_device_auth(session, code)
        tokens = fs.get_tokens()
        # Save tokens somewhere for next time

        # Get children
        children = await fs.get_children()
        felix = children["Felix"]

        # Read schedule
        schedule = await felix.get_schedule()
        print(schedule)

        # Add 30 min today
        await felix.add_allowance_today(minutes=30)

        # Set Monday to 1 hour
        await felix.set_allowance("monday", minutes=60)

asyncio.run(main())
```

---

## Notes

- Only **Windows** screen time is currently supported
- `allowance=0` means the device is **blocked** (no screen time)
- The available window controls *when* the device can be used (even if allowance > 0)
- Data refreshes every 5 minutes in Home Assistant

---

## Acknowledgements

This project was inspired by [pyfamilysafety](https://github.com/Mycrosys-Solutions/pyfamilysafety) by Mycrosys-Solutions (archived Feb 2026). That library pioneered the reverse-engineering of the Microsoft Family Safety mobile aggregator API — in particular the endpoint discovery and the `dailyRestrictions` data shape. This project builds on that groundwork with a rewritten architecture, device code flow authentication, and a tighter focus on Home Assistant integration.

---

## License

MIT
