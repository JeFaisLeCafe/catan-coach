# This project is GPL-3.0 because Catanatron is

Catanatron is GPL-3.0-or-later, and we link against it, so `catan-coach` is a derivative work
and is licensed GPL-3.0-or-later too. This was accepted knowingly rather than discovered late.

What it permits: running a public website on top of this. GPL-3.0 is not AGPL, so letting
people interact with the software over a network is not distribution and triggers no obligation
to publish anything.

What it restricts: shipping an artifact to anyone — a desktop app, a Docker image, a published
package, a binary — is distribution, and the recipient must receive GPL-3.0 source. Closed-source
or commercial distribution is not an option while this dependency stands.

Since the eventual goal is a website rather than a product, this is a live but non-blocking
constraint. If distribution ever becomes the goal, the escape route is replacing the engine
adapter (see ADR 0001), not relicensing.
