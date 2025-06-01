# Guide for Filling Out the General Order Acknowledgement (GOA) Form

## Introduction

This guide is designed to help new project managers in the packaging manufacturing industry properly complete the General Order Acknowledgement (GOA) form. The GOA is a critical document that captures all specifications and requirements for a machine build, serving as the main reference during kickoff meetings and throughout the project lifecycle.

## General Approach

1. **Start with the Quote**: Most information in the GOA comes directly from the customer's quote/sales order. Always refer to this document first.
2. **Consult the URS**: If a User Requirement Specification (URS) exists, use it to supplement information from the quote.
3. **When in Doubt**: If information is missing or unclear, consult with Sales, Engineering, or reach out to the customer for clarification.
4. **During Kickoff**: Be prepared to modify the GOA during the kickoff meeting as specifications are confirmed.

## Section-by-Section Guide

### 1. Basic Information

- **Proj. #**: The unique project identifier assigned by your company (Example: "Ax")
- **Customer**: The end client's company name
- **Machine**: The type of machine being built (e.g., Filler, Capper, etc.)
- **Direction**: The machine's flow direction (typically left-to-right or right-to-left)

### 2. Order Identification

All information in this section should come directly from the quote/sales order:

- **Purchase Order #**: Customer's PO number
- **Quote #**: Your company's quote number
- **Internal Order #**: Your company's internal order number (Example: "Ox")
- **Customer #**: Customer ID in your system
- **COR's**: Change order requests (if applicable)
- **Revision**: Current revision of the document
- **Production speed**: The agreed-upon production speed (bottles per minute)
- **URS Applicable Y/N**: Whether a User Requirement Specification document exists
- **Ref. Project**: Any reference project this build is based on
- **Date / Version**: Current date and document version

### 3. Utility Specifications

These specifications determine the electrical and pneumatic requirements:

- **Voltage**: Supply voltage (e.g., 208-240V)
- **Hz**: Frequency (typically 50Hz or 60Hz)
- **PSI**: Required air pressure (typically 80-100 PSI)
- **Conformity**: Certification standards (None, CSA, etc.)
- **Certification**: Special certification requirements:
  - None
  - CSA
  - CE
  - Explosion
  - Class1 Div 2
- **Country of destination**: Where the machine will be installed (affects electrical standards)

> **IMPORTANT**: For explosion-proof environments, certain electrical components must be substituted with pneumatic equivalents. For example, tank level sensors must be pneumatic rather than electrical.

### 4. Change Part Quantities and Construction Materials

This section defines quantities and materials for components that may need to be changed for different product formats:

- **Bottle**: Specify quantity and material (HDPE, etc.) and options such as Linear Index
- **Plug**: Quantity and material (SS 304, SS 316, etc.)
- **Cap**: Quantity and material, including options like Urethane Insert
- **Elevator Slats**: Quantity and material (Aluminum or other)
- **Seal Material**: Quantity and type (PTFE/Teflon, Viton, Silicone, Buna, EPDM)
  - Specify who selects: Capmatic or Customer
- **Tubing Material**: Quantity and type (Polyethylene, Braided PVC, Silicone, etc.)
  - Specify who selects: Capmatic or Customer
- **Filling Nozzles**: Specify the set quantity

### 5. Material Specifications

This section defines materials that come in contact with the product:

- **Filling Neck Locators**: Typically made from FDA-approved materials
- **Tablet**: Quantity and material (Acetal, 316L, etc.)
- **Desiccant**: Quantity and material (Polycarbonate, etc.)
- **Cotton**: Quantity and material (Pet-P, etc.)
- **Product Metal Contact Parts**: Usually SS 304 or SS 316L based on product compatibility
- **Label**: Quantity, number of peel plates, and belt specifications
- **Tooling ID**: Identification method (Bx, Cx, Lx or Customer Code)
- **Tooling Cart**: Yes/No
- **Direct Product Contact**: Specify requirements (Autoclavable, Material Certification, Electropolished)

> **TIP**: Material choices made during the GOA stage can be modified during the kickoff if necessary, but getting it right initially saves time.

### 6. Option Listing, Remarks, Critical Points, and Notes

Use these text areas to document:
- **Option Listing**: List all optional features being included
- **Remarks / Special Design**: Document any special design requirements
- **Critical URS Compliance Points**: Note any critical requirements from the URS
- **Production Notes**: Include any special production considerations

### 7. Control & Programming Specifications

This section defines the machine's control system:

- **Explosion proof**: Specify if required or None
- **PLC**: Select the appropriate controller type:
  - B & R
  - CompactLogix
  - Allen Bradley
  - ControlLogix
  - Other
- **HMI**: Specify the human-machine interface:
  - Allen Bradley (PV+ 7", PV+ 10")
  - B & R (with PC Upgrade option)
  - Size (5.7", 10", 15")
  - Language (English, French)
  - Location (Infeed Side, Outfeed Side, Operator side, Rear)
- **Control Panel Post**: Select based on machine type and layout:
  - 1-Axis: Simple machines with one movement direction
  - 2-Axis/3-Axis: More complex machines with multiple movement directions
  - Fixed: Standard option for most applications
  - STD for Explosive Environment: For hazardous environments
- **Beacon Light Tower**: Visual indicators:
  - Select colors (Red, Green, Yellow)
  - Audible option for sound alerts
- **Extra E-Stops**: Additional emergency stop buttons
  - Specify quantity and locations if required
- **Batch / Data Report**: Reporting capabilities:
  - None
  - Yes (requires 15" HMI)
  - Type (Summary Page only, Summary Header with Tracking)
  - Audit Trail (with File Name)
  - Memory Expansion Module
- **Additional Features**:
  - Remote Technical Service (None, Connection Only)
  - Customer Specific Wiring Code
  - Electronic Torque Readout w/10"HMI
  - Clear Bottle Sensor
  - Tank/Hopper Level Output Signal (Pneumatic, 24V)

### 8. Bottle Handling System Specifications

This section defines how bottles/containers are fed into the machine:

- **Tube**: Feeding options for tubes:
  - Vibratory Feeder
  - Outfeed Chute
  - Acoustic Cover
  - Pedestal Vibratory
  - Mechanical Feeder
  - Outfeed Track
  - Bulk Elevator
- **Vial / Bottle**: Container handling options:
  - Infeed/Outfeed Tray
  - Infeed/Outfeed Conveyor
  - Transfer Guides
  - Double Side Belts
  - Bottle Unscrambler
  - Full Conveyor
  - Bottle Bulk Elevator
- **Puck System**: For unstable containers:
  - De-Pucker System
  - Puck Return System
  - Infeed/Outfeed Conveyor
  - Quantity of Pucks
  - Formats for Pucks
- **Turn Tables**: For manual or semi-automatic loading:
  - Infeed/Outfeed with or without tray
  - Buffer
  - Orientor
  - Size options (39", 48", 60")
- **Index / Motion**: Container movement mechanisms:
  - Single/Double Index
  - Walking Beam
  - Feed Screw
  - Rake
  - Starwheel
  - Gating
  - Single/Dual Belt
  - Bottle Aligner

> **NOTE**: When filling out this section, refer to the machine layout drawing to understand how products flow through the system.

### 9. Reject / Inspection System

This section specifies how rejected products are handled:

- **Reject Method**: How rejects are removed from the line:
  - Chute
  - Lockable
  - Track
  - Linear
  - Conveyor
  - Tray
  - Starwheel
  - High Speed
- **Reject Reasons**: What conditions trigger rejection:
  - Fill Weight / Count
  - No Cotton
  - Cap Presence
  - Stem Presence
  - Various component presence checks
  - High/Cross Thread
  - Torque
  - Vision system rejections (OCV, OCR, Bar Code)
  - Label issues (Position, Presence)
  - Sleeve Presence
  - UV Presence

### 10. Street Fighter Tablet Counter

For tablet counting systems:

- **Street Fighter model**: Version (1, 2, 100)
- **No. Of Funnels**: Quantity (1, 2, 5)
- **Cleaning STN**: If cleaning station is included
- **Hopper**: Size options (10L, 60L, 100L) and features (Dust Extraction)
- **Lift Fighter**: Options for the lift mechanism:
  - No Air
  - Load Cells
  - Int. Dust Collection
  - Interlocked
  - Twin Axis HMI

### 11. Liquid Filling System Specifications

For filling machines, this section is critical:

- **Pump**: Type of pump mechanism:
  - Volumetric
  - Steel Heart (Peristaltic)
- **Type**: Filling mechanism:
  - Pneumatic
  - Liquid/Semi
  - Servo Bottom-Up fill
  - Servo (QTY)
  - Viscous
  - Positive Displacement
- **Pump Volume**: Size options:
  - 10cc (QTY)
  - 50cc (QTY)
  - 100cc (QTY)
  - 250cc (QTY)
  - 500cc (QTY)
  - 850cc (QTY)
  - 1000cc (QTY)
  - Mass Meter (QTY)
  - Hard Chrome
- **Valve type**: Valve mechanism:
  - None
  - Ball Weight
  - Rotary
  - Air Pilot
- **Nozzle type**: Nozzle design:
  - Straight
  - Straight with check valve
  - IBSO (Internal Bottom Shut Off)
  - OBSO (Outside Bottom Shut Off)
  - Double wall – Nitro & Fill
- **Nozzle Body Size**: Diameter options:
  - 6 mm, 8mm, 10mm, 12mm
  - Fractional sizes (½", ⅜", ¾")
- **Nozzle Bar / Stations**: Configuration of nozzle placement
  - Offset Nozzle bar
- **Centering Device**: How bottles are centered:
  - None
  - Cone
  - Neck
- **Tank / Hopper / Infeed Hose**: Product supply configuration:
  - Tank or Hopper
  - Agitator
  - Spray Ball
  - Electropolished
  - Size options (18L, 60L, 100L)
  - Jacketed
  - Transfer Pump
  - Customer Hose Size specifications
- **Gutter System**: For catching drips:
  - None
  - Drip Style
  - Prime/Purge/Rinse
- **Cleaning**: Cleaning systems:
  - None
  - Ionization Cleaning
  - Vacuum Air Cleaning
  - Touch & Go (C.I.P. Man. SYS)
- **Options**: Additional features:
  - Check Weighing (Tare in/out)
  - Number of Cells

> **TIP**: For size-appropriate nozzles, measure the neck opening and select a diameter 2-3mm smaller. If multiple bottle formats share one nozzle set, use the smallest appropriate diameter.

### 12. Gas Purge (if applicable)

For products requiring oxygen removal:

- **None**: If no gas purge is required
- **Type**: Gas selection (Nitrogen, Argon)
- **Location / Type**: Application points:
  - Before Fill ST
  - AT Fill ST
  - After Fill
  - Tunnel
  - QTY (quantity of purge points)

### 13. Desiccant

For systems that insert desiccant:

- **None**: If no desiccant is used
- **Type**: Form of desiccant:
  - Roll / Pouch
  - Cannister
- **Bulk feeder**: How desiccant is fed:
  - Internal
  - Pedestal Vibratory
  - Elevator
  - Cover

### 14. Cottoner

For systems that insert cotton:

- **None**: If no cotton inserter is used
- **Sensing**: Detection options:
  - Presence
  - High
- **Cotton Bin**: Cotton storage:
  - Yes
  - None

### 15. Plugging System Specifications

For machines that insert plugs:

- **Plug Placement**: Mechanism for inserting plugs:
  - Push Through
  - Pick & Place
  - Vacuum
  - Mechanical
  - Rotary
- **Plug Sorting**: How plugs are oriented:
  - None
  - Mechanical
  - Centrifugal
  - Vibratory Bowl
  - Docking Station
  - Acoustic Cover
  - Elevator
- **Bulk Feeder**: How plugs are supplied:
  - None
  - Pedestal Vibratory
  - Pneumatic
  - Capacity (cubic feet)
  - Elevator (Giraffe)
  - Electric

### 16. Capping System Specifications

For machines that apply caps:

- **Cap Placement**:
  - Push Through
  - Pick & Place
  - Rotation
  - Air
  - Servo
  - Servo Index
  - Servo Up Down
  - On the Fly
- **Torque**: Torque application mechanism:
  - Air motor
  - Magnet clutch
  - Servo
  - Feedback
  - Torque Range (in-lbs)
  - Servo Calibration System
  - Application Torque System Tool
- **Cap Sorting**: How caps are oriented:
  - Centrifugal
  - Vibratory Bowl
  - Docking Station
  - Acoustic Cover
  - Elevator
  - Mechanical
- **Centering Device**: How bottles are centered:
  - None
  - Cone
  - Tube
  - Neck
- **Tube Aligner**: For tube applications:
  - None
  - Cone
  - Grip & Dive
- **Bulk Feeder**: How caps are supplied:
  - None
  - Pedestal Vibratory
  - Elevator (Giraffe)
  - Capacity (cubic feet)
  - Cover

> **NOTE**: A servo with a magnetic clutch is not standard and should be verified if both appear in the quote.

### 17. BeltStar System Specifications

For belt-driven capping systems:

- **Cap Placement**:
  - None
  - Belts – on the fly
  - AC
- **Torque**: Torque mechanism:
  - Air motor
  - Magnet clutch
  - Servo
  - Belts
  - Torque Range (in-lbs)
  - AC motor DC Brake
  - Feedback
  - HMI Adj. Torque
  - Application Torque System Tool
- **Cap Sorting**:
  - Elevator
  - Docking Station
- **Motorized Adj.**:
  - None
  - Yes

### 18. Labeling System Specifications

For labeling machines:

- **Label HD model**:
  - LS100: For labels up to 100mm wide
  - LS200: For labels up to 200mm wide
- **Support reel DIA.**:
  - 300 mm
  - 380 mm
- **Arm type**:
  - Standard
  - "L" shaped
- **Application SYS**:
  - Wrap around
  - 3-Panel
  - 4-Panel
  - 5-Panel
  - Case label
  - Wipe Front & Back
  - Prism
  - Wrap around in Puck
  - Belts QTY
- **Label Head Orientation**:
  - Low Label Sense
  - Eagle Eye Sensor (CLR label)
  - Type (Linear/Inline, Rotary)
  - DX (right-hand)
  - SX (left-hand)
- **Separator Wheel**:
  - None
  - Belt
  - Wheel
  - Starwheel
- **Top Hold Down**:
  - Bottle Aligner
  - Twin Feedscrew

### 19. Coding and Inspection System Specifications

For printing batch codes, expiration dates, or other variable information:

- **None**: If no coding system is required
- **Coder**:
  - Hot stamp
  - Make & Model
  - Extra Foil Cassette Holder
  - Extra Character Holders
  - Startup Kit
  - Thermal Transfer
  - Laser
  - Thermal Ink jet
- **Additional Ink**:
  - Ink Jet Clean. Sol.
- **Videojet**:
  - Dataflex models (6330, 6530)
  - For DX (RH) for SX (LH)
  - 8520
  - Ink jet VJ 1520
  - Laser 3330
- **Laser**:
  - Videojet
  - Other
  - Fume Extraction
  - Model
  - Customer supplied
- **Vision**:
  - None
  - Cognex
  - Other
  - QTY
  - OCR
  - OCV
  - Barcode
  - Orientation/Skew
  - Presence
  - Position
- **Print**:
  - On Bottle
  - On Web
  - Lot
  - Bar Code
  - Exp. Date
  - 2D
  - Package On
  - Other

### 20. Synergy Excise Tax Labeller 12 (Bottle)

For tax stamp application systems:

- **2 Bottle Orientation SYS**: For bottle positioning
- **8 HD P/P Servo**: For pick and place servos
- **1 Mag w/12 Rows**: Magnet configuration
- **1 Adhesive Station (2-nozzle)**: Adhesive application
- **Inspection**:
  - Top
  - Side
  - Corner
- **Application**:
  - Cap & Body

### 21. Induction Specifications

For induction sealing systems:

- **Enercon Model**:
  - 500
  - 700
- **Voltage**:
  - 200 to 240
- **HZ**:
  - 50
  - 60
- **Sealing HD c/w IO Cable**:
  - Tunnel
  - Flat (LM)
- **Stand (Enercon)**:
  - Fixed
  - Mobile
- **Status Light**:
  - Enercon
- **Separator Wheel**:
  - Capmatic
  - Capmatic Reject Bin (Only) Enercon Reject Peg
- **Cap Inspection From Enercon**:
  - None
  - Stalled Bottle
  - Crooked Cap
- **No Foil**:
  - None
  - Enercon
  - Capmatic m/c
- **Compact Head (Rotary)**: For rotary applications

### 22. Retorquer

For re-tightening caps after induction:

- **Beltsar Model**: Model specification
- **Features**:
  - Belt driven torqueing system
  - Torque adjustable via the touch screen control (HMI)
  - No air required
  - One (X 1) motorized pair of tightening belts
  - Torque is controlled with a limiting device coupled with a loadcell

### 23. Shrink Sleeve Specifications

For shrink sleeve applicators:

- **Sleever Application Area**:
  - Neck Appl'n
  - Body Appl'n
  - Full Body Appl'n
  - Photo Registration
- **Band Tacker**: For band tacking
- **Sleeve Pres. Sensor**:
  - None
  - Non-UV
  - UV
- **Perforation**:
  - Vertical Perf.
  - Horizontal Perf.
- **Sleever**:
  - Pneumatic Set-down
  - Rotary Brush Set-down
- **Shrink Tunnel**:
  - From 3rd Party
  - SS Tunnel
  - Auto lift Device
  - 24in Long
  - 28in Long
  - Single Gun (3.5KW)
  - Double Gun (3.5KW)
  - Angle adjustment system
  - HMI temp Monitor

### 24. Conveyor Specifications

- **Width**:
  - 3¼"
  - 4½"
  - 7½"
  - Other
- **Length O.L**:
  - Infeed
  - Outfeed
  - Single
- **Height**:
  - 36" (standard)
  - Other
- **Shape**:
  - Straight
  - U
  - 90°
- **Chain Type**:
  - STD
  - Anti-Static (for load cells)
  - High Temp
- **Bed Type**:
  - Standard
  - Raised Bed
- **Layout #**: Reference number
- **Tunnel Guard**:
  - None
  - Infeed
  - Outfeed
- **Transf. Guide**:
  - None
  - Infeed
  - Outfeed
- **Wirecovers**:
  - None
  - 4-section wireway
  - Trough
- **Bottle Transfer**:
  - Conveyor Infeed (End, Machine Side, Oper. Side)
  - Conveyor Outfeed (End, Machine Side, Oper. Side)

### 25. Euro Guarding

For machine guarding requirements:

- **None**: If no special guarding is required
- **Panel material**:
  - Lexan
  - Tempered glass
- **Switch type**:
  - Key switch
  - Magnetic
  - Other
- **Reject Cover**:
  - None
  - Yes
- **Top Cover**:
  - None
  - Yes
- **Customer Location Dim**:
  - Room HT
  - Room Doorway HT
  - Room Doorway W

### 26. Fat & Sample Requirements

For factory acceptance testing:

- **FAT**: Factory Acceptance Testing
- **Formats**: Format specifications
- **Duration (min)**: Test duration
- **Sample Return to**:
  - Customer
  - Capmatic

### 27. Manual Specifications

Documentation requirements:

- **Language**:
  - English
  - French
  - Other
- **Contact Material Certification**:
  - Yes
  - No
- **Calibration Certification**:
  - Yes
  - No
- **Preventive Maintenance Program**:
  - Yes
  - No
- **Type**:
  - Electronic
  - Paper
- **Quantity**: Number of copies

### 28. Validation Documents

Required documentation:

- **FAT**: Factory Acceptance Testing docs
- **SAT**: Site Acceptance Testing docs
- **DQ**: Design Qualification
- **HDS/SDS**: Hardware/Software Design Specification
- **FS/DS**: Functional/Design Specification
- **IQ/OQ**: Installation/Operational Qualification
- **Language**:
  - English
  - French
  - Other

### 29. Packaging & Transport

Shipping arrangements:

- **Transport charges**:
  - Capmatic
  - Customer
  - Customer / Not Incl.
- **Packaging by**:
  - Capmatic
  - Customer / Not Incl.
- **Packaging type**:
  - Skid
  - Crate
  - Sea Worthy

### 30. Warranty & Install & Spares

Support options:

- **Warranty**:
  - 1YR
  - 2YR
- **Spares Kit**:
  - None
  - 1YR
  - 2YR
- **Remote Tech. Service**:
  - None
  - Yes
- **Start-up Commissioning**:
  - None
  - Yes
- **Comments - Cut & Paste from Quote**: Space for quote information

### 31. Revision Log

Document change tracking:

- **Revision ID**: Revision identifier
- **Date**: Revision date
- **Description**: Change description
- **By**: Person responsible for changes

## Best Practices

1. **Be Thorough**: Missing information leads to assumptions that may be incorrect
2. **Highlight Critical Requirements**: Use the "Option Listing" and "Remarks" sections to emphasize key points
3. **Consult with Experts**: When uncertain about technical specifications, consult with Engineering
4. **Document Changes**: Use the revision log to track modifications
5. **Review Before Kickoff**: Thoroughly review the completed GOA before the kickoff meeting

## Common Pitfalls to Avoid

1. **Material Compatibility Issues**: Not verifying product compatibility with selected materials
2. **Contradictory Specifications**: Specifying options that don't work together (e.g., servo and magnetic clutch)
3. **Missing Technical Requirements**: Overlooking critical specifications from the URS
4. **Unrealistic Speed Requirements**: Not confirming that the specified speed is achievable with the selected components
5. **Overlooking Facility Constraints**: Not accounting for customer's facility limitations (ceiling height, door width, etc.)

## Conclusion

The GOA is a living document that serves as the foundation for the entire project. Taking time to complete it thoroughly and accurately will prevent costly changes and delays later in the project lifecycle. When in doubt, always consult with the relevant department or the customer directly to ensure all specifications are correct. 