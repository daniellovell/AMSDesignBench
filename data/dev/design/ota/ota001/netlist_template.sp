* Five-Transistor OTA Design Template for SKY130 PDK
* Fill in all BLANK parameters based on specifications

* Specifications (MUST fill in exact values from design brief):
.param VDD=BLANK
.param CL=BLANK

* Transistor dimensions (DESIGN using Gm/ID tables):
* IMPORTANT: Do NOT use 'u' suffix on L/W (write L1=0.5 not L1=0.5u)
* Each transistor can have independent L and W
.param L1=BLANK W1=BLANK
.param L2=BLANK W2=BLANK
.param Lp1=BLANK Wp1=BLANK
.param Lp2=BLANK Wp2=BLANK
.param Ltail=BLANK Wtail=BLANK

* Input voltage sources (DESIGN the DC common-mode voltage):
* For AC analysis: set DC to your chosen VCM, AC amplitude for differential signal
Vinp vinp 0 DC BLANK AC 0.5
Vinn vinn 0 DC BLANK AC -0.5

* Tail current bias voltage (DESIGN to work with your chosen input VCM):
Vbias_n vbias_n 0 DC BLANK

* Five-transistor OTA topology:
XM1 n1 vinp ntail 0 sky130_fd_pr__nfet_01v8 L=L1 W=W1 nf=1
XM2 vout vinn ntail 0 sky130_fd_pr__nfet_01v8 L=L2 W=W2 nf=1
XMp2 n1 n1 vdd vdd sky130_fd_pr__pfet_01v8 L=Lp2 W=Wp2 nf=1
XMp1 vout n1 vdd vdd sky130_fd_pr__pfet_01v8 L=Lp1 W=Wp1 nf=1
XMtail ntail vbias_n 0 0 sky130_fd_pr__nfet_01v8 L=Ltail W=Wtail nf=1
