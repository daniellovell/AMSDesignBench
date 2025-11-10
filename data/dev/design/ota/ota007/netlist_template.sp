* Simple CS with Active Load OTA Design Template for SKY130 PDK
* Fill in all BLANK parameters based on specifications

* Specifications (MUST fill in exact values from design brief):
* Specifications (MUST fill in exact values from design brief):
.param VDD=BLANK
.param CL=BLANK

* Transistor dimensions (DESIGN using Gm/ID tables):
* IMPORTANT: Do NOT use 'u' suffix on L/W
* Each transistor has independent L and W for design freedom
.param L2=BLANK W2=BLANK
.param L1=BLANK W1=BLANK

* Input voltage sources (DESIGN the DC common-mode voltage):
Vin vin 0 DC BLANK AC 1.0



* Bias voltages (DESIGN for proper operation):
Vb1 vb1 0 DC BLANK

* OTA Topology:
XM2 vout vin 0 0 sky130_fd_pr__nfet_01v8 L=L2 W=W2 nf=1
XM1 VDD vb1 vout VDD sky130_fd_pr__pfet_01v8 L=L1 W=W1 nf=1
