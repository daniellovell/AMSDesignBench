* Telescopic Cascode Single-Ended OTA Design Template for SKY130 PDK
* Fill in all BLANK parameters based on specifications

* Specifications (MUST fill in exact values from design brief):
* Specifications (MUST fill in exact values from design brief):
.param VDD=BLANK
.param CL=BLANK

* Transistor dimensions (DESIGN using Gm/ID tables):
* IMPORTANT: Do NOT use 'u' suffix on L/W
* Each transistor has independent L and W for design freedom
.param L3=BLANK W3=BLANK
.param L4=BLANK W4=BLANK
.param L1=BLANK W1=BLANK
.param L2=BLANK W2=BLANK
.param L5=BLANK W5=BLANK
.param L6=BLANK W6=BLANK
.param L7=BLANK W7=BLANK
.param L8=BLANK W8=BLANK
.param L9=BLANK W9=BLANK

* Input voltage sources (DESIGN the DC common-mode voltage):
Vin vin 0 DC BLANK AC 1.0



* Bias voltages (DESIGN for proper operation):
Vb3 vb3 0 DC BLANK
Vtail vtail 0 DC BLANK

* OTA Topology:
XM3 N004 vip N006 0 sky130_fd_pr__nfet_01v8 L=L3 W=W3 nf=1
XM4 N005 vin N006 0 sky130_fd_pr__nfet_01v8 L=L4 W=W4 nf=1
XM1 vop vb3 N005 0 sky130_fd_pr__nfet_01v8 L=L1 W=W1 nf=1
XM2 N003 vb3 N004 0 sky130_fd_pr__nfet_01v8 L=L2 W=W2 nf=1
XM5 N006 vtail 0 0 sky130_fd_pr__nfet_01v8 L=L5 W=W5 nf=1
XM6 N003 N003 N001 VDD sky130_fd_pr__pfet_01v8 L=L6 W=W6 nf=1
XM7 vop N003 N002 VDD sky130_fd_pr__pfet_01v8 L=L7 W=W7 nf=1
XM8 N001 N001 VDD VDD sky130_fd_pr__pfet_01v8 L=L8 W=W8 nf=1
XM9 N002 N001 VDD VDD sky130_fd_pr__pfet_01v8 L=L9 W=W9 nf=1
