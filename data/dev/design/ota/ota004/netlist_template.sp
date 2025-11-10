* Two-Stage Miller OTA Design Template for SKY130 PDK
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
.param L5=BLANK W5=BLANK
.param L6=BLANK W6=BLANK
.param L7=BLANK W7=BLANK

* Input voltage sources (DESIGN the DC common-mode voltage):
Vinp vinp 0 DC 0.9 AC 0.5
Vinn vinn 0 DC 0.9 AC -0.5



* Bias voltages (DESIGN for proper operation):
Vbn vbn 0 DC BLANK
Vbp vbp 0 DC BLANK

* OTA Topology:
XM1 n1 vinp ntail 0 sky130_fd_pr__nfet_01v8 L=L1 W=W1 nf=1
XM2 vint vinn ntail 0 sky130_fd_pr__nfet_01v8 L=L2 W=W2 nf=1
XM3 n1 n1 vdd vdd sky130_fd_pr__pfet_01v8 L=L3 W=W3 nf=1
XM4 vint n1 vdd vdd sky130_fd_pr__pfet_01v8 L=L4 W=W4 nf=1
XM5 ntail vbn 0 0 sky130_fd_pr__nfet_01v8 L=L5 W=W5 nf=1
XM6 vout vint 0 0 sky130_fd_pr__nfet_01v8 L=L6 W=W6 nf=1
XM7 vout vbp vdd vdd sky130_fd_pr__pfet_01v8 L=L7 W=W7 nf=1
