# tap2go Embedded

This repository contains the code for the tap2go embedded bike tracking module.

## Prerequisites

- disable kernel serial connection usage (using `raspi-config`)

To run the system, you will need to wire up a FONA808 to the serial ports
as well as wire up an RGB LED. The exact pin numbers are in the source code.

## Installation

Installation is quite straight-forward. Assuming a raspberry pi on python 3.6:

```bash
> git clone https://github.com/dragorhast/embedded.git
> cd embedded
> pipenv install
```

There is also a daemon file that is recommended, which is coming soon.
