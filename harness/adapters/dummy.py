"""Dummy (mock) adapter that returns canned answers for testing."""

from typing import Any, Dict, List
from .base import BaseAdapter

SYS_PROMPT = """You are an analog circuit design expert. Please provide circuit analysis as requested."""

DUMMY_ANSWER = """
### Observations
The amplifier uses negative feedback [M1, R_f] with a single-ended topology [M1] and an inverting configuration.

### Calculations
1. Low-frequency closed-loop gain: Acl ≈ –Rf/R1 [R_f, R1]
2. Bandwidth depends on the dominant pole set by Rf and parasitic capacitances [R_f, C_gd].

### Answer
GBW is set by gm/CL; exceptions like feedforward/current-steering change the relation. CMFB loop should be slower and compensated at its amp when present.
"""

# Functional dummy designs for SKY130 (VDD=1.8V)
# These are designed to be FUNCTIONAL, not to match old-process references
# Goal: Reasonable gain (20-40dB), moderate current (~50-200uA), stable
DESIGN_TEMPLATES = {
    "feedback001": """
```spice
* feedback001 - TIA with resistive feedback (structure-only dummy)
XU2 S_in 0 S_out opamp Aol=100K GBW=10Meg
R1 S_out S_in 10k
.end
```
""",
    "feedback002": """
```spice
* feedback002 - TIA with capacitive feedback (structure-only dummy)
XU2 S_in 0 S_out opamp Aol=100K GBW=10Meg
C1 S_out S_in 100p
.end
```
""",
    "feedback003": """
```spice
* feedback003 - Non-inverting amplifier (structure-only dummy)
XU1 N001 S_in S_out opamp Aol=100K GBW=10Meg
R1 0 N001 10k
R2 S_out N001 90k
.end
```
""",
    "feedback004": """
```spice
* feedback004 - Inverting amplifier (structure-only dummy)
XU2 N001 0 S_out opamp Aol=100K GBW=10Meg
R1 S_out N001 100k
R2 N001 S_in 10k
.end
```
""",
    "ota001": """
```spice
* OTA001 - Five-Transistor (FUNCTIONAL for SKY130 - 31.5dB)
.param VDD=1.8
.param CL=5p
.param L1=1.0 W1=15
.param L2=1.0 W2=15
.param Lp1=1.0 Wp1=35
.param Lp2=1.0 Wp2=30
.param Ltail=1.5 Wtail=8
Vinp vinp 0 DC 0.9 AC 0.5
Vinn vinn 0 DC 0.9 AC -0.5
Vbias_n vbias_n 0 DC 0.7
XM1 n1 vinp ntail 0 sky130_fd_pr__nfet_01v8 L=L1 W=W1 nf=1
XM2 vout vinn ntail 0 sky130_fd_pr__nfet_01v8 L=L2 W=W2 nf=1
XMtail ntail vbias_n 0 0 sky130_fd_pr__nfet_01v8 L=Ltail W=Wtail nf=1
XMp2 n1 n1 vdd vdd sky130_fd_pr__pfet_01v8 L=Lp2 W=Wp2 nf=1
XMp1 vout n1 vdd vdd sky130_fd_pr__pfet_01v8 L=Lp1 W=Wp1 nf=1
```
""",
    "ota002": """
```spice
* OTA002 - Telescopic Cascode (FUNCTIONAL: 51.2 dB with pin-swap fix)
Vinp vip 0 DC 0.9 AC 0.5
Vinn vin 0 DC 0.9 AC -0.5
Vb1 vb1 0 DC 0.3
Vb2 vb2 0 DC 0.5
Vb3 vb3 0 DC 1.3
Vtail vtail 0 DC 0.8
XM3 N003 vip N005 0 sky130_fd_pr__nfet_01v8 L=1.0 W=50 nf=1
XM4 N004 vin N005 0 sky130_fd_pr__nfet_01v8 L=1.0 W=50 nf=1
XM2 voutn vb3 N003 0 sky130_fd_pr__nfet_01v8 L=1.0 W=45 nf=1
XM1 voutp vb3 N004 0 sky130_fd_pr__nfet_01v8 L=1.0 W=45 nf=1
XM5 N005 vtail 0 0 sky130_fd_pr__nfet_01v8 L=1.5 W=65 nf=1
XM6 N001 vb2 voutn vdd sky130_fd_pr__pfet_01v8 L=1.0 W=75 nf=1
XM7 N002 vb2 voutp vdd sky130_fd_pr__pfet_01v8 L=1.0 W=75 nf=1
XM8 VDD vb1 N001 vdd sky130_fd_pr__pfet_01v8 L=1.0 W=100 nf=1
XM9 VDD vb1 N002 vdd sky130_fd_pr__pfet_01v8 L=1.0 W=100 nf=1
```
""",
    "ota003": """
```spice
* OTA003 - High-Swing Single Stage (FUNCTIONAL for SKY130)
.param VDD=1.8
.param CL=5p
.param L_in=1.0 W_in=15
.param L_tail=1.5 W_tail=8
.param L_pmir=1.0 W_pmir=30
.param L_phis=1.0 W_phis=35
.param L_ncs=0.8 W_ncs=18
.param L_pcs=0.8 W_pcs=35
Vinp vinp 0 DC 0.9 AC 0.5
Vinn vinn 0 DC 0.9 AC -0.5
Vbias_n vbias_n 0 DC 0.7
Vbias_ncs vbias_ncs 0 DC 0.55
Vbias_p vbias_p 0 DC 1.0
XM1 n1 vinp ntail 0 sky130_fd_pr__nfet_01v8 L=L_in W=W_in nf=1
XM2 n2 vinn ntail 0 sky130_fd_pr__nfet_01v8 L=L_in W=W_in nf=1
XMtail ntail vbias_n 0 0 sky130_fd_pr__nfet_01v8 L=L_tail W=W_tail nf=1
XM3 n1 n1 vdd vdd sky130_fd_pr__pfet_01v8 L=L_pmir W=W_pmir nf=1
XM4 n2 n1 vdd vdd sky130_fd_pr__pfet_01v8 L=L_pmir W=W_pmir nf=1
XM5 nmir n2 vdd vdd sky130_fd_pr__pfet_01v8 L=L_phis W=W_phis nf=1
XM6 vout n2 vdd vdd sky130_fd_pr__pfet_01v8 L=L_phis W=W_phis nf=1
XM7 nmir vbias_ncs 0 0 sky130_fd_pr__nfet_01v8 L=L_ncs W=W_ncs nf=1
XM8 vout vbias_ncs 0 0 sky130_fd_pr__nfet_01v8 L=L_ncs W=W_ncs nf=1
```
""",
    "ota004": """
```spice
* OTA004 - Two-Stage Miller (FUNCTIONAL for SKY130: 21.7dB, 8MHz, 72°PM)
.param VDD=1.8
.param CL=5p
.param L1=1.0 W1=20
.param L2=1.0 W2=20
.param L3=1.0 W3=40
.param L4=1.0 W4=40
.param L5=1.5 W5=10
.param L6=0.8 W6=80
.param L7=1.0 W7=80
Vinp vinp 0 DC 0.9 AC 0.5
Vinn vinn 0 DC 0.9 AC -0.5
Vbn vbn 0 DC 0.75
Vbp vbp 0 DC 0.7
XM1 n1 vinp ntail 0 sky130_fd_pr__nfet_01v8 L=L1 W=W1 nf=1
XM2 vint vinn ntail 0 sky130_fd_pr__nfet_01v8 L=L2 W=W2 nf=1
XM3 n1 n1 vdd vdd sky130_fd_pr__pfet_01v8 L=L3 W=W3 nf=1
XM4 vint n1 vdd vdd sky130_fd_pr__pfet_01v8 L=L4 W=W4 nf=1
XM5 ntail vbn 0 0 sky130_fd_pr__nfet_01v8 L=L5 W=W5 nf=1
XM6 vout vint 0 0 sky130_fd_pr__nfet_01v8 L=L6 W=W6 nf=1
XM7 vout vbp vdd vdd sky130_fd_pr__pfet_01v8 L=L7 W=W7 nf=1
```
""",
    "ota005": """
```spice
* OTA005 - Telescopic Cascode SE (dummy; matches `data/dev/design/ota/ota005/netlist_template.sp`)
.param VDD=1.8
.param CL=10p
.param L3=0.18 W3=100
.param L4=0.18 W4=100
.param L1=0.18 W1=80
.param L2=0.18 W2=80
.param L5=0.18 W5=80
.param L6=0.18 W6=100
.param L7=0.18 W7=100
.param L8=0.18 W8=100
.param L9=0.18 W9=100

Vip vip 0 DC 0.6 AC -0.5
Vin vin 0 DC 0.6 AC 0.5
Vb3 vb3 0 DC 1.20
Vtail vtail 0 DC 1.15

XM3 N004 vip N006 0 sky130_fd_pr__nfet_01v8 L=L3 W=W3 nf=1
XM4 N005 vin N006 0 sky130_fd_pr__nfet_01v8 L=L4 W=W4 nf=1
XM1 vout vb3 N005 0 sky130_fd_pr__nfet_01v8 L=L1 W=W1 nf=1
XM2 N003 vb3 N004 0 sky130_fd_pr__nfet_01v8 L=L2 W=W2 nf=1
XM5 N006 vtail 0 0 sky130_fd_pr__nfet_01v8 L=L5 W=W5 nf=1
XM6 N003 N003 N001 vdd sky130_fd_pr__pfet_01v8 L=L6 W=W6 nf=1
XM7 vout N003 N002 vdd sky130_fd_pr__pfet_01v8 L=L7 W=W7 nf=1
XM8 N001 N001 vdd vdd sky130_fd_pr__pfet_01v8 L=L8 W=W8 nf=1
XM9 N002 N001 vdd vdd sky130_fd_pr__pfet_01v8 L=L9 W=W9 nf=1
```
""",
    "ota006": """
```spice
* OTA006 - Telescopic High-Swing SE (dummy; matches `data/dev/design/ota/ota006/netlist_template.sp`)
.param VDD=1.8
.param CL=10p
.param L3=0.18 W3=10
.param L4=0.18 W4=10
.param L1=0.18 W1=8
.param L2=0.18 W2=8
.param L5=0.18 W5=8
.param L6=0.18 W6=20
.param L7=0.18 W7=20
.param L8=0.18 W8=24
.param L9=0.18 W9=24

Vip vip 0 DC 0.9 AC -0.5
Vin vin 0 DC 0.9 AC 0.5
Vb1 vb1 0 DC 0.70
Vb2 vb2 0 DC 1.20
Vtail vtail 0 DC 0.85

XM3 N004 vip N006 0 sky130_fd_pr__nfet_01v8 L=L3 W=W3 nf=1
XM4 N005 vin N006 0 sky130_fd_pr__nfet_01v8 L=L4 W=W4 nf=1
XM1 vout vb2 N005 0 sky130_fd_pr__nfet_01v8 L=L1 W=W1 nf=1
XM2 N001 vb2 N004 0 sky130_fd_pr__nfet_01v8 L=L2 W=W2 nf=1
XM5 N006 vtail 0 0 sky130_fd_pr__nfet_01v8 L=L5 W=W5 nf=1
XM6 vout vb1 N003 vdd sky130_fd_pr__pfet_01v8 L=L6 W=W6 nf=1
XM7 N001 vb1 N002 vdd sky130_fd_pr__pfet_01v8 L=L7 W=W7 nf=1
XM8 N003 N001 vdd vdd sky130_fd_pr__pfet_01v8 L=L8 W=W8 nf=1
XM9 N002 N001 vdd vdd sky130_fd_pr__pfet_01v8 L=L9 W=W9 nf=1
```
""",
    "ota007": """
```spice
* OTA007 - Simple CS Active Load (FUNCTIONAL for SKY130 - 28.7dB)
.param VDD=1.8
.param CL=5p
.param L_nmos=0.8 W_nmos=15
.param L_pmos=0.8 W_pmos=40
Vin vin 0 DC 0.9 AC 1.0
Vb1 vb1 0 DC 0.4
XM2 vout vin 0 0 sky130_fd_pr__nfet_01v8 L=L_nmos W=W_nmos nf=1
XM1 vdd vb1 vout vdd sky130_fd_pr__pfet_01v8 L=L_pmos W=W_pmos nf=1
```
""",
    "ota008": """
```spice
* OTA008 - Cascode SE (FUNCTIONAL: 46.4 dB, 156.5 MHz)
Vin vin 0 DC 0.8 AC 1.0
Vb1 vb1 0 DC 1.2
Vb2 vb2 0 DC 0.25
Vb3 vb3 0 DC 0.5
XM1 N002 vin 0 0 sky130_fd_pr__nfet_01v8 L=0.5 W=50 nf=1
XM2 vout vb1 N002 0 sky130_fd_pr__nfet_01v8 L=0.5 W=50 nf=1
XM3 vout vb2 N001 vdd sky130_fd_pr__pfet_01v8 L=0.5 W=75 nf=1
XM4 N001 vb3 vdd vdd sky130_fd_pr__pfet_01v8 L=0.5 W=100 nf=1
```
""",
    "ota009": """
```spice
* OTA009 - Gain-Boosted Cascode (FUNCTIONAL for SKY130: 81.6dB, 20.5MHz, 87.9°PM)
* Fixed template: M8 body connected to VDD (was floating at n003)
.param VDD=1.8
.param CL=5p
Vin vin 0 DC 0.6038 AC 1.0
Vb1 vb1 0 DC 0.3583
Vb2 vb2 0 DC 0.3072
Vb3 vb3 0 DC 0.8003
* Original template topology with corrected M8 body + optimized biasing
XM1 n005 vin 0 0 sky130_fd_pr__nfet_01v8 L=0.5 W=50 nf=1
XM2 vout n004 n005 0 sky130_fd_pr__nfet_01v8 L=0.5 W=50 nf=1
XM3 n001 n002 vout vdd sky130_fd_pr__pfet_01v8 L=0.5 W=75 nf=1
XM4 vdd vb3 n001 vdd sky130_fd_pr__pfet_01v8 L=0.5 W=100 nf=1
XM7 vdd n001 n002 vdd sky130_fd_pr__pfet_01v8 L=0.5 W=100 nf=1
XM8 vdd vb1 n004 vdd sky130_fd_pr__pfet_01v8 L=0.8 W=82 nf=1
XM5 n004 n005 0 0 sky130_fd_pr__nfet_01v8 L=0.8 W=11 nf=1
XM6 n002 vb2 0 0 sky130_fd_pr__nfet_01v8 L=1.0 W=1 nf=1
```
""",
    "ota010": """
```spice
* OTA010 - Folded Cascode Diff PMOS (FUNCTIONAL for SKY130: 65.2dB gain)
.param VDD=1.8
.param CL=10p
.param L1=1.0 W1=48
.param L2=1.0 W2=48
.param L3=1.0 W3=48
.param L4=1.0 W4=48
.param L5=1.0 W5=48
.param L6=1.0 W6=48
.param L7=1.0 W7=48
.param L8=1.0 W8=24
.param L9=1.5 W9=18
.param L10=1.0 W10=24
.param L11=1.5 W11=18
Vinp vinp 0 DC 0.9 AC 0.5
Vinn vinn 0 DC 0.9 AC -0.5
Vb1 vb1 0 DC 0.60
Vb2 vb2 0 DC 0.50
Vb3 vb3 0 DC 0.43
Vb4 vb4 0 DC 1.15
Vb5 vb5 0 DC 1.05
XM1 n001 vinn n005 vdd sky130_fd_pr__pfet_01v8 L=L1 W=W1 nf=1
XM2 n001 vinp n004 vdd sky130_fd_pr__pfet_01v8 L=L2 W=W2 nf=1
XM3 vdd vb1 n001 vdd sky130_fd_pr__pfet_01v8 L=L3 W=W3 nf=1
XM4 vdd vb5 n002 vdd sky130_fd_pr__pfet_01v8 L=L4 W=W4 nf=1
XM5 vdd vb5 n003 vdd sky130_fd_pr__pfet_01v8 L=L5 W=W5 nf=1
XM6 n002 vb4 vout vdd sky130_fd_pr__pfet_01v8 L=L6 W=W6 nf=1
XM7 n003 vb4 voutn vdd sky130_fd_pr__pfet_01v8 L=L7 W=W7 nf=1
XM8 voutn vb3 n004 0 sky130_fd_pr__nfet_01v8 L=L8 W=W8 nf=1
XM9 n004 vb2 0 0 sky130_fd_pr__nfet_01v8 L=L9 W=W9 nf=1
XM10 vout vb3 n005 0 sky130_fd_pr__nfet_01v8 L=L10 W=W10 nf=1
XM11 n005 vb2 0 0 sky130_fd_pr__nfet_01v8 L=L11 W=W11 nf=1
```
""",
    "ota011": """
```spice
* OTA011 - Folded Cascode SE HS PMOS (FUNCTIONAL: 67.1 dB, 0.3 MHz)
Vinp vinp 0 DC 0.7 AC 0.5
Vinn vinn 0 DC 0.7 AC -0.5
Vb1 vb1 0 DC 0.8
Vb2 vb2 0 DC 0.6
Vb3 vb3 0 DC 0.55
Vb4 vb4 0 DC 1.0
XM1 N002 vinn N006 vdd sky130_fd_pr__pfet_01v8 L=0.5 W=20 nf=1
XM2 N002 vinp N005 vdd sky130_fd_pr__pfet_01v8 L=0.5 W=20 nf=1
XM3 vdd vb1 N002 vdd sky130_fd_pr__pfet_01v8 L=0.5 W=26 nf=1
XM4 vdd N001 N003 vdd sky130_fd_pr__pfet_01v8 L=0.5 W=30 nf=1
XM5 vdd N001 N004 vdd sky130_fd_pr__pfet_01v8 L=0.5 W=30 nf=1
XM6 N003 vb4 N001 vdd sky130_fd_pr__pfet_01v8 L=0.5 W=30 nf=1
XM7 N004 vb4 vout vdd sky130_fd_pr__pfet_01v8 L=0.5 W=30 nf=1
XM8 vout vb3 N005 0 sky130_fd_pr__nfet_01v8 L=0.5 W=14 nf=1
XM9 N005 vb2 0 0 sky130_fd_pr__nfet_01v8 L=0.5 W=10 nf=1
XM10 N001 vb3 N006 0 sky130_fd_pr__nfet_01v8 L=0.5 W=14 nf=1
XM11 N006 vb2 0 0 sky130_fd_pr__nfet_01v8 L=0.5 W=10 nf=1
```
""",
    "ota012": """
```spice
* OTA012 - Folded Cascode Castail PMOS (FUNCTIONAL for SKY130: 33.4dB, 8.9kHz, 96°PM)
.param VDD=1.8
.param CL=10p
.param L1=1.0 W1=72
.param L2=1.0 W2=72
.param L3=1.0 W3=72
.param L4=1.0 W4=63
.param L5=1.0 W5=72
.param L6=1.0 W6=72
.param L7=1.0 W7=72
.param L8=1.0 W8=44
.param L9=1.5 W9=26
.param L10=1.0 W10=44
.param L11=1.5 W11=26
.param L12=1.0 W12=81
Vinp vinp 0 DC 0.9 AC 0.5
Vinn vinn 0 DC 0.9 AC -0.5
Vb1 vb1 0 DC 0.55
Vb2 vb2 0 DC 0.46
Vb3 vb3 0 DC 0.647
Vb4 vb4 0 DC 1.023
Vb5 vb5 0 DC 0.904
XM1 n004 vinn n006 vdd sky130_fd_pr__pfet_01v8 L=L1 W=W1 nf=1
XM2 n004 vinp n005 vdd sky130_fd_pr__pfet_01v8 L=L2 W=W2 nf=1
XM3 vdd vb1 n002 vdd sky130_fd_pr__pfet_01v8 L=L3 W=W3 nf=1
XM4 vdd n001 n001 vdd sky130_fd_pr__pfet_01v8 L=L4 W=W4 nf=1
XM5 vdd n001 n003 vdd sky130_fd_pr__pfet_01v8 L=L5 W=W5 nf=1
XM6 n001 vb4 vb4 vdd sky130_fd_pr__pfet_01v8 L=L6 W=W6 nf=1
XM7 n003 vb4 vout vdd sky130_fd_pr__pfet_01v8 L=L7 W=W7 nf=1
XM8 vout vb3 n005 0 sky130_fd_pr__nfet_01v8 L=L8 W=W8 nf=1
XM9 n005 vb2 0 0 sky130_fd_pr__nfet_01v8 L=L9 W=W9 nf=1
XM10 vb4 vb3 n006 0 sky130_fd_pr__nfet_01v8 L=L10 W=W10 nf=1
XM11 n006 vb2 0 0 sky130_fd_pr__nfet_01v8 L=L11 W=W11 nf=1
XM12 n002 vb5 n004 vdd sky130_fd_pr__pfet_01v8 L=L12 W=W12 nf=1
```
""",
}


FILTER_DESIGNS = {
    "filter001": """
```spice
* FILTER001 - First-order RC low-pass filter
* fc = 1/(2πRC) = 15.9 kHz
Vin vin 0 AC 1
R1 vin vout 1k
C1 vout 0 10n
```
""",
    "filter002": """
```spice
* FILTER002 - First-order CR high-pass filter
* fc = 1/(2πRC) = 15.9 kHz
Vin vin 0 AC 1
C1 vin vout 10n
R1 vout 0 1k
```
""",
    "filter003": """
```spice
* FILTER003 - First-order RL low-pass filter
* fc = R/(2πL) = 796 Hz
Vin vin 0 AC 1
L1 vin vout 10m
R1 vout 0 50
```
""",
    "filter004": """
```spice
* FILTER004 - Second-order passive RLC band-pass filter (FUNCTIONAL)
* f0 = 50.3 kHz, Q = 3.16 (properly designed)
* Parallel RLC topology for accurate Q
Vin vin 0 AC 1
Rin vin vout 1e12
L1 vout 0 1.001302e-03
C1 vout 0 9.998601e-09
Rload vout 0 1000
```
""",
    "filter005": """
```spice
* FILTER005 - Fourth-order cascaded active biquad low-pass filter
* Stage 1: f01 = 10 kHz, Stage 2: f02 = 15 kHz
Vin vin 0 AC 1
R1A vin n1 1.59k
R2A n1 v1 1.59k
C1A n1 0 10n
C2A v1 n1 10n
XU1 v1 n1 0 OPAMP

R1B v1 n2 1.06k
R2B n2 vout 1.06k
C1B n2 0 10n
C2B vout n2 10n
XU2 vout n2 0 OPAMP

Rload vout 0 10k

.end
```
""",
    "filter006": """
```spice
* FILTER006 - Fourth-order cascaded active biquads with independent tuning
* Stage 1: f01 = 8 kHz, Q1 = 0.707; Stage 2: f02 = 12 kHz, Q2 = 1.0
Vin vin 0 AC 1
R1A vin n1 2k
R2A n1 v1 2k
C1A n1 0 10n
C2A v1 n1 10n
XU1 v1 n1 0 OPAMP

R1B v1 n2 1.33k
R2B n2 vout 1.33k
C1B n2 0 10n
C2B vout n2 10n
XU2 vout n2 0 OPAMP

Rload vout 0 10k

.end
```
""",
    "filter007": """
```spice
* FILTER007 - First-order RL low-pass filter
* fc = R/(2πL) = 796 Hz
Vin vin 0 AC 1
L1 vin vout 10m
R1 vout 0 50
Rload vout 0 1k

.end
```
""",
    "filter008": """
```spice
* FILTER008 - First-order all-pass filter using op-amp
* f0 = 1/(2πRC) = 15.9 kHz (R=1k, C=10n)
Vin vin 0 AC 1
R1 vin npos 1k
C1 npos 0 10n
* All-pass condition: R2 = R3
R2 vin nneg 1k
R3 vout nneg 1k
XU1 vout nneg npos OPAMP
Rload vout 0 10k

.end
```
""",
    "filter009": """
```spice
* FILTER009 - Passive twin-T notch filter (band-stop)
* f0 = 1/(2πRC) = 15.9 kHz, Q ≈ 0.5
Vin vin 0 AC 1
R1 vin nA 1k
R2 nA vout 1k
Cmid nA 0 20n
C1 vin nB 10n
C2 nB vout 10n
Rmid nB 0 500
Rload vout 0 10k

.end
```
""",
    "filter010": """
```spice
* FILTER010 - Second-order high-pass filter
* fc = 15.9 kHz, Q = 1.0
Vin vin 0 AC 1
C1 vin n1 10n
C2 n1 vout 10n
R1 n1 0 1k
R2 vout 0 1k
XU1 vout vout n1 OPAMP
Rload vout 0 10k

.end
```
""",
    "filter011": """
```spice
* FILTER011 - Dummy band-pass (matches `data/dev/design/filters/filter011/netlist_template.sp`)
Vin vin 0 AC 1
L1 vin n1 10m
C1 n1 vraw 25.33n
Rbp vraw 0 125.7
Rg nneg 0 10k
Rfb vout nneg 10k
XU1 vout nneg vraw OPAMP
Rload vout 0 10k

.end
```
""",
    "filter012": """
```spice
* FILTER012 - Dummy band-pass (matches `data/dev/design/filters/filter012/netlist_template.sp`)
Vin vin 0 AC 1
L1 vin n1 10m
C1 n1 vraw 25.33n
Rbp vraw 0 314.2
XU1 vout vout vraw OPAMP
Rload vout 0 10k

.end
```
""",
}

class DummyAdapter(BaseAdapter):
    name = "dummy"

    def predict(self, batch: List[Dict[str, Any]]) -> List[str]:
        import json
        from pathlib import Path
        
        outs: List[str] = []
        for item in batch:
            prompt = item.get("prompt", "")
            question = item.get("question", {})
            qid = question.get("id", "")
            
            # Check if this is a multiple choice question
            prompt_variant = question.get("meta", {}).get("prompt_variant", "short_form")
            if prompt_variant == "multiple_choice":
                # Load MC answer key and return the correct answer
                item_dir_str = item.get("item_dir", "")
                if item_dir_str:
                    item_dir = Path(item_dir_str)
                    aspect = question.get("meta", {}).get("aspect", "")
                    
                    # Determine MC answer key filename
                    mc_key_name = "mc_answer_key.json"
                    if aspect and question.get("track") == "analysis":
                        mc_key_name = f"mc_answer_key_{aspect}.json"
                    
                    mc_key_path = item_dir / mc_key_name
                    if mc_key_path.exists():
                        try:
                            mc_data = json.loads(mc_key_path.read_text(encoding='utf-8'))
                            correct_letter = mc_data.get("correct_answer", "A")
                            # Return the correct answer letter
                            outs.append(f"The correct answer is: {correct_letter}")
                            continue
                        except Exception:
                            pass
                
                # Fallback: just answer "A"
                outs.append("The correct answer is: A")
                continue
            
            # Check if this is a design question with verification
            is_design_verification = (
                (question.get("track") == "design" and (question.get("verification") or {}).get("enabled")) or
                ("design" in qid and "verification" in qid) or
                ("design" in prompt.lower() and ("ota" in prompt.lower() or "filter" in prompt.lower() or "blank" in prompt.lower()))
            )
            
            if is_design_verification:
                # Determine OTA or filter type from question ID
                design_id = None
                
                # Check for feedback designs
                for i in range(1, 5):
                    if f"feedback{i:03d}" in qid:
                        design_id = f"feedback{i:03d}"
                        template = DESIGN_TEMPLATES.get(design_id, DESIGN_TEMPLATES["feedback001"])
                        outs.append(template)
                        break

                # Check for OTA
                if design_id is None:
                    for i in range(1, 13):
                        if f"ota{i:03d}" in qid:
                            design_id = f"ota{i:03d}"
                            template = DESIGN_TEMPLATES.get(design_id, DESIGN_TEMPLATES["ota001"])
                            outs.append(template)
                            break
                
                # Check for filter if not OTA
                if design_id is None:
                    for i in range(1, 13):
                        if f"filter{i:03d}" in qid:
                            design_id = f"filter{i:03d}"
                            template = FILTER_DESIGNS.get(design_id, FILTER_DESIGNS["filter001"])
                            outs.append(template)
                            break
                
                # Fallback if neither matched
                if design_id is None:
                    outs.append(DUMMY_ANSWER)
            else:
                # Default: use template for analysis/debugging questions
                inv_ids = item.get("inventory_ids", [])
                cite1 = inv_ids[0] if inv_ids else "M1"
                cite2 = inv_ids[1] if len(inv_ids) > 1 else "CL"
                filled = DUMMY_ANSWER.replace("M1", cite1).replace("R_f, R1", f"{cite1}, {cite2}")
                outs.append(filled)
        return outs


def build(**kwargs) -> DummyAdapter:
    return DummyAdapter()
