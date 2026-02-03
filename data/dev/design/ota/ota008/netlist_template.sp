* Cascode Single-Ended OTA Design Template for SKY130 PDK
* Fill in all BLANK parameters based on specifications

* Specifications (MUST fill in exact values from design brief):
* Specifications (MUST fill in exact values from design brief):
.param VDD=BLANK
.param CL=BLANK

* Transistor dimensions (DESIGN using Gm/ID tables):
* IMPORTANT: Do NOT use 'u' suffix on L/W
* Each transistor has independent L and W for design freedom
.param L1=BLANK W1=BLANK
.param L2=BLANK W2=BLANK
.param L3=BLANK W3=BLANK
.param L4=BLANK W4=BLANK

* Input voltage sources (DESIGN the DC common-mode voltage):
Vin vin 0 DC BLANK AC 1.0



* Bias voltages (DESIGN for proper operation):
Vb1 vb1 0 DC BLANK
Vb2 vb2 0 DC BLANK
Vb3 vb3 0 DC BLANK

* OTA Topology:
XM1 N002 vin 0 0 sky130_fd_pr__nfet_01v8 L=L1 W=W1 nf=1
XM2 vout vb1 N002 0 sky130_fd_pr__nfet_01v8 L=L2 W=W2 nf=1
XM3 N001 vb2 vout VDD sky130_fd_pr__pfet_01v8 L=L3 W=W3 nf=1
XM4 VDD vb3 N001 VDD sky130_fd_pr__pfet_01v8 L=L4 W=W4 nf=1
