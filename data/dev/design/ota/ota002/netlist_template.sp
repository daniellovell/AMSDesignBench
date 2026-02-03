* Telescopic Cascode OTA Design Template for SKY130 PDK
* Fill in all BLANK parameters based on specifications

* Specifications (MUST fill in exact values from design brief):
.param VDD=BLANK
.param CL=BLANK

* Transistor dimensions (DESIGN using Gm/ID tables):
* Input differential pair (M3, M4)
.param L_in=BLANK W_in=BLANK

* NMOS cascode devices (M1, M2)
.param L_ncas=BLANK W_ncas=BLANK

* Tail current source (M5)
.param L_tail=BLANK W_tail=BLANK

* PMOS cascode devices (M6, M7)
.param L_pcas=BLANK W_pcas=BLANK

* PMOS current mirror load (M8, M9)
.param L_pload=BLANK W_pload=BLANK

* Input voltage sources (DESIGN the DC common-mode voltage):
* For AC analysis: set DC to your chosen VCM, AC amplitude for differential signal
Vinp vinp 0 DC BLANK AC 0.5
Vinn vinn 0 DC BLANK AC -0.5

* Bias voltages (DESIGN these for proper cascoding and current levels):
Vb1 vb1 0 DC BLANK
Vb2 vb2 0 DC BLANK
Vb3 vb3 0 DC BLANK
Vtail vtail 0 DC BLANK

* Telescopic Cascode OTA Topology (fully differential):
* Input pair with cascodes
XM3 n003 vinp n005 0 sky130_fd_pr__nfet_01v8 L=L_in W=W_in nf=1
XM4 n004 vinn n005 0 sky130_fd_pr__nfet_01v8 L=L_in W=W_in nf=1
XM2 voutn vb3 n003 0 sky130_fd_pr__nfet_01v8 L=L_ncas W=W_ncas nf=1
XM1 voutp vb3 n004 0 sky130_fd_pr__nfet_01v8 L=L_ncas W=W_ncas nf=1
XM5 n005 vtail 0 0 sky130_fd_pr__nfet_01v8 L=L_tail W=W_tail nf=1

* PMOS cascodes and current mirror load
XM6 voutn vb2 n001 vdd sky130_fd_pr__pfet_01v8 L=L_pcas W=W_pcas nf=1
XM7 voutp vb2 n002 vdd sky130_fd_pr__pfet_01v8 L=L_pcas W=W_pcas nf=1
XM8 n001 vb1 vdd vdd sky130_fd_pr__pfet_01v8 L=L_pload W=W_pload nf=1
XM9 n002 vb1 vdd vdd sky130_fd_pr__pfet_01v8 L=L_pload W=W_pload nf=1

