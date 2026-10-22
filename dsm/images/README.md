# DSM Screenshots

**Source:** Real screenshots supplied by the owner on 2026-10-22, documenting the existing installation on the lab's current physical hardware.

- `dsm-version.png` — DSM version dialog; no visual changes.
- `rr-model-platform.png` — supplied crop showing DS3622xs+ and broadwellnk; no visual changes or identifying data requiring redaction.
- `dsm-info-center-reference-redacted.png` — Information Center reference, cropped through the memory row and with the serial value covered by an opaque black rectangle. Its displayed CPU identity, clock and core count are not the real host/VM hardware inventory; the guide explains this limitation.
- `proxmox-hardware-redacted.png` — Hardware; the physical disk value and network MAC are covered with opaque black rectangles.
- `proxmox-options-redacted.png` — Options; the complete SMBIOS/UUID value is covered with an opaque black rectangle.

These are not generated interfaces. Every retained, unmasked RGBA pixel is unchanged from its source; masked pixels were verified fully opaque and black. Image metadata was stripped. Unredacted originals and validation manifests remain in ignored `dsm/.local/`, outside the public documentation.

See the [installation guide](../docs/installation-guide.md) for configuration details, evidence limits and the incomplete manual procedure.
