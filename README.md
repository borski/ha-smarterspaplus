# SmarterSpa+ for Home Assistant

Home Assistant integration for the ControlOMatic SmarterSpa+ saltwater chlorinator. ControlOMatic is out of business and the official app is gone from both app stores. The device still talks to its Firebase backend, and so does this integration.

Cloud polling only. No Bluetooth.

## Install

Requires Home Assistant 2026.10.1 or newer. That's the oldest version tested.

### HACS custom repository

1. Open HACS, then its menu, then **Custom repositories**.
2. Add `https://github.com/borski/ha-smarterspaplus` with type **Integration**.
3. Find **SmarterSpa+** in HACS and download it.
4. Restart Home Assistant.
5. Open **Settings > Devices & services > Add integration** and select **SmarterSpa+**.

The GitHub repository must be public and contain the integration files before installation works. This is a custom repository, not a HACS default-store listing.

### Manual installation

Copy `custom_components/smarterspa` into your Home Assistant `config/custom_components/` directory and restart.

Then add the integration from Settings, Devices & Services. It asks for the email and password you used in the SmarterSpa+ app.

Home Assistant saves the login in its config entry, as readable credential values. Protect the config directory and backups. Credentials don't belong in this repository or logs.

### Updates and validation

HACS can install from the default branch without a release archive. For versioned updates, publish a GitHub release whose tag matches the integration's `manifest.json` version. Restart HA after an integration update.

GitHub Actions runs HACS validation and Home Assistant's hassfest after pushes and pull requests. The repository needs a description, topics, and enabled issues on GitHub. License validation is deliberately excluded until a license is selected. Default-store submission is a separate step.

## Entities

| Entity | Type | Source |
|---|---|---|
| Power level | sensor and number (1 to 10) | `Main.p` |
| Salt status | sensor, OK or Low | `Main.s` |
| Electrode life remaining | sensor, percent | 100 minus `Main.e` |
| Zero point | sensor and number (10 to 150) | `Settings.z` |
| Chlorine generation | switch | `Main.g` |
| Device lights | switch | `Settings.l` |
| Firmware | diagnostic sensor | `Pass.v` |
| Last boot | diagnostic timestamp | `Pass.t` |
| Service version | diagnostic sensor | last `Feed.v` reply, exact component meaning unverified |
| Check for updates | button | writes `Uc` |

Polling is every 30 seconds, and every 2 seconds for up to 10 seconds after a command. Fast polling ends early when the inbox is empty and the requested state matches. An update check uses the full window because a cached reply can't prove a fresh response.

Overlapping commands from this integration are rejected while confirmation is pending. A nonempty cloud inbox also blocks writes. This doesn't prevent another app from writing between the inbox read and PATCH. Avoid using both clients to issue commands simultaneously. A timeout doesn't prove a command failed. Check state before retrying.

## Not available over the cloud

- Chlorine sensor millivolts. The device never publishes them to Firestore.
- Online or offline state. Nothing in the document changes while the device idles.
- Salt status codes other than 0 and 1. Unmapped codes show as unknown with the raw code in an attribute.

## Commands

Only allowlisted strings from the reference are written. They go into the document's `Input` field. Observed inbox consumption was within a second, but state changes can take longer.

| Action | String |
|---|---|
| Chlorine on | `V1.1.8.B+` |
| Chlorine off | `V1.1.8.B-` |
| Lights on / off | `L+` / `L-` |
| Power level n | `V1.1.8.P+n/` |
| Zero point n | `Zzn/` |
| Update check | `Uc` |

## Longevity

The Firebase project runs on the defunct company's Google Cloud billing. If that lapses, sign-in and reads start failing and this integration goes unavailable. The device keeps chlorinating on its own regardless.
