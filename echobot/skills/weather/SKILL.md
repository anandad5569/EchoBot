---
description: Get current weather and forecasts on Linux and Windows (no
  API key required).
homepage: "https://wttr.in/:help"
metadata:
  echo:
    emoji: 🌤️
name: weather
---

# Weather

Cross-platform weather lookup for **Linux** and **Windows**.

## Platform notes

-   **Linux / macOS / Git Bash**: use `curl`
-   **Windows PowerShell**: use `curl.exe` instead of `curl`
-   In PowerShell, bare `curl` may resolve to `Invoke-WebRequest`, which
    can cause prompts or parsing issues
-   For JSON APIs on Windows, `Invoke-RestMethod` is often the cleanest
    option

------------------------------------------------------------------------

## wttr.in (primary)

Free, no API key, returns text or images.

### Current weather

**Linux / macOS**

``` bash
curl -fsSL "https://wttr.in/London?format=3"
# Output: London: ⛅️ +8°C
```

**Windows PowerShell**

``` powershell
curl.exe -s "https://wttr.in/London?format=3"
# Output: London: ⛅️ +8°C
```

### Compact format

**Linux / macOS**

``` bash
curl -fsSL "https://wttr.in/London?format=%l:+%c+%t+%h+%w"
# Output: London: ⛅️ +8°C 71% ↙5km/h
```

**Windows PowerShell**

``` powershell
curl.exe -s "https://wttr.in/London?format=%l:+%c+%t+%h+%w"
# Output: London: ⛅️ +8°C 71% ↙5km/h
```

### Full forecast

**Linux / macOS**

``` bash
curl -fsSL "https://wttr.in/London?T"
```

**Windows PowerShell**

``` powershell
curl.exe -s "https://wttr.in/London?T"
```

### Current only

**Linux / macOS**

``` bash
curl -fsSL "https://wttr.in/London?0"
```

**Windows PowerShell**

``` powershell
curl.exe -s "https://wttr.in/London?0"
```

### Today only

**Linux / macOS**

``` bash
curl -fsSL "https://wttr.in/London?1"
```

**Windows PowerShell**

``` powershell
curl.exe -s "https://wttr.in/London?1"
```

### Save PNG

**Linux / macOS**

``` bash
curl -fsSL "https://wttr.in/Berlin.png" -o /tmp/weather.png
```

**Windows PowerShell**

``` powershell
curl.exe -s "https://wttr.in/Berlin.png" -o "$env:TEMP\weather.png"
```

### Format codes

-   `%c` condition\
-   `%t` temperature\
-   `%h` humidity\
-   `%w` wind\
-   `%l` location\
-   `%m` moon

### Tips

-   URL-encode spaces: `wttr.in/New+York`
-   Airport codes: `wttr.in/JFK`
-   Units: `?m` (metric), `?u` (USCS)
-   Use full URLs (`https://`) for better cross-platform compatibility

------------------------------------------------------------------------

## Open-Meteo (fallback, JSON)

Good for programmatic use.

### Query JSON

**Linux / macOS**

``` bash
curl -fsSL "https://api.open-meteo.com/v1/forecast?latitude=51.5&longitude=-0.12&current_weather=true"
```

**Windows PowerShell**

``` powershell
Invoke-RestMethod -Uri "https://api.open-meteo.com/v1/forecast?latitude=51.5&longitude=-0.12&current_weather=true"
```

Find coordinates for a city first, then query the forecast.\
Returns JSON with temperature, wind speed, and weather code.

Docs: https://open-meteo.com/en/docs

------------------------------------------------------------------------

## Recommended usage rules for agents

-   On **Linux**, prefer:

``` bash
curl -fsSL "https://wttr.in/<CITY>?format=3"
```

-   On **Windows PowerShell**, prefer:

``` powershell
curl.exe -s "https://wttr.in/<CITY>?format=3"
```

-   Avoid bare `curl` in PowerShell (may map to `Invoke-WebRequest`)
-   If JSON is needed on Windows, prefer `Invoke-RestMethod`
