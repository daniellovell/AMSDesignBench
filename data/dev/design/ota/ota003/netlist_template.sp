* High-Swing Single-Stage OTA Design Template for SKY130 PDK
* Fill in all BLANK parameters based on specifications

* Specifications (MUST fill in exact values from design brief):
.param VDD=BLANK
.param CL=BLANK

* Transistor dimensions (DESIGN using Gm/ID tables):
* Input differential pair (M1, M2)
.param L_in=BLANK W_in=BLANK

* Tail current source (Mtail)
.param L_tail=BLANK W_tail=BLANK

* PMOS current mirror (M3, M4 - diode-connected and mirror)
.param L_pmir=BLANK W_pmir=BLANK

* PMOS high-swing current mirror (M5, M6 - additional stage)
.param L_phis=BLANK W_phis=BLANK

* Second stage NMOS CS (M6)
.param L_ncs=BLANK W_ncs=BLANK

* Second stage PMOS load (M7)
.param L_pcs=BLANK W_pcs=BLANK

* Input voltage sources (DESIGN the DC common-mode voltage):
Vinp vinp 0 DC BLANK AC 0.5
Vinn vinn 0 DC BLANK AC -0.5

* Bias voltages (DESIGN these):
Vbias_n vbias_n 0 DC BLANK
Vbias_ncs vbias_ncs 0 DC BLANK
Vbias_p vbias_p 0 DC BLANK

* High-Swing Single-Stage OTA Topology:
* Input differential pair
XM1 n1 vinp ntail 0 sky130_fd_pr__nfet_01v8 L=L_in W=W_in nf=1
XM2 n2 vinn ntail 0 sky130_fd_pr__nfet_01v8 L=L_in W=W_in nf=1
XMtail ntail vbias_n 0 0 sky130_fd_pr__nfet_01v8 L=L_tail W=W_tail nf=1

* PMOS current mirror (diode-connected)
XM3 n1 n1 vdd vdd sky130_fd_pr__pfet_01v8 L=L_pmir W=W_pmir nf=1
XM4 n2 n1 vdd vdd sky130_fd_pr__pfet_01v8 L=L_pmir W=W_pmir nf=1

* High-swing output path (additional PMOS mirrors)
XM5 nmir n1 vdd vdd sky130_fd_pr__pfet_01v8 L=L_phis W=W_phis nf=1
XM6 vout n1 vdd vdd sky130_fd_pr__pfet_01v8 L=L_phis W=W_phis nf=1

* NMOS current sink/load
XM7 nmir nmir 0 0 sky130_fd_pr__nfet_01v8 L=L_ncs W=W_ncs nf=1
XM8 vout nmir 0 0 sky130_fd_pr__nfet_01v8 L=L_ncs W=W_ncs nf=1

