# Supplied CAD archive inspection for AY-04

Source supplied by user (kept outside this repository):
`/home/ayush/TOPS/[.] idk/dual-arm-robots-1.snapshot.2.zip`.
SHA-256: `efbd131a321d4f6a2535487f5a1d1acab54d1c200e171c028eaed0402adc7071`.
`unzip -t` passed for all 15 entries. The manifest contains four JPG previews,
`SDA_20D.stp`, SolidWorks part files (`.SLDPRT`), and two SolidWorks assemblies
(`.SLDASM`). The four previews show a dual-arm robot assembly and mounting
base, not a five-station machine-tending workcell. The STEP header names
`SDA_20D.stp`, records a 2010 Siemens NX export, and declares millimetres via
`SI_UNIT(.MILLI.,.METRE.)`; that unit applies to the STEP model, **not** to
the repository's station positions. The SolidWorks assemblies were not opened
in a CAD system, so their exact dimensions and internal reference frames
remain unverified.

No explicit `RAW_INPUT`/staging/CNC/output/finished station coordinates,
world/base-frame convention, or dimensioned five-station layout is provided
by the visible archive manifest, STEP header, or preview images. The ZIP
therefore cannot justify replacing the temporary AY-04 station values in
`src/carrier_control/config/machine_tending.json`. No CAD file, image, or
archival experiment was copied into the repository, and no station value was
changed in response to this upload.

To update AY-04 with measured geometry, request a dimensioned workcell layout
or table with each station origin and orientation relative to a specified
`world`/UR5 `base_link` frame, units, box/interaction dimensions, and the
`RAW_PICK`, staging, machine load/unload, output, and finished target locations.
The supplied dual-arm assembly may be relevant to later module/flange work,
but its geometry must be opened and measured in appropriate CAD software
before using any of it as a sourced dimension.
