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
* OTA004 - Two-Stage Miller (FUNCTIONAL for SKY130)
.param VDD=1.8
.param CL=20p
.param L1=1.0 W1=20
.param L2=1.0 W2=20
.param L3=1.0 W3=50
.param L4=1.0 W4=50
.param L5=1.5 W5=12
.param L6=0.5 W6=80
.param L7=1.0 W7=80
Vinp vinp 0 DC 0.9 AC 0.5
Vinn vinn 0 DC 0.9 AC -0.5
Vbn vbn 0 DC 0.7
Vbp vbp 0 DC 1.0
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
* OTA005 - Telescopic Cascode SE (FUNCTIONAL for SKY130)
.param VDD=1.8
.param CL=10p
.param L3=0.8 W3=18
.param L4=0.8 W4=18
.param L1=0.8 W1=18
.param L2=0.8 W2=18
.param L5=1.5 W5=10
.param L6=0.8 W6=40
.param L7=0.8 W7=40
.param L8=0.8 W8=40
.param L9=0.8 W9=40
Vin vin 0 DC 0.9 AC 1.0
Vb3 vb3 0 DC 0.6
Vtail vtail 0 DC 0.65
XM3 N004 vin N006 0 sky130_fd_pr__nfet_01v8 L=L3 W=W3 nf=1
XM4 N005 vin N006 0 sky130_fd_pr__nfet_01v8 L=L4 W=W4 nf=1
XM1 vop vb3 N005 0 sky130_fd_pr__nfet_01v8 L=L1 W=W1 nf=1
XM2 N003 vb3 N004 0 sky130_fd_pr__nfet_01v8 L=L2 W=W2 nf=1
XM5 N006 vtail 0 0 sky130_fd_pr__nfet_01v8 L=L5 W=W5 nf=1
XM6 N003 N003 N001 vdd sky130_fd_pr__pfet_01v8 L=L6 W=W6 nf=1
XM7 vop N003 N002 vdd sky130_fd_pr__pfet_01v8 L=L7 W=W7 nf=1
XM8 N001 N001 vdd vdd sky130_fd_pr__pfet_01v8 L=L8 W=W8 nf=1
XM9 N002 N001 vdd vdd sky130_fd_pr__pfet_01v8 L=L9 W=W9 nf=1
```
""",
    "ota006": """
```spice
* OTA006 - Telescopic High-Swing SE (FUNCTIONAL for SKY130)
.param VDD=1.8
.param CL=10p
.param L3=0.8 W3=18
.param L4=0.8 W4=18
.param L1=0.8 W1=18
.param L2=0.8 W2=18
.param L5=1.5 W5=10
.param L6=0.8 W6=40
.param L7=0.8 W7=40
.param L8=0.8 W8=40
.param L9=0.8 W9=40
Vinp vip 0 DC 0.9 AC 0.5
Vinn vin 0 DC 0.9 AC -0.5
Vb1 vb1 0 DC 1.0
Vb2 vb2 0 DC 0.6
Vtail vtail 0 DC 0.65
XM3 N004 vip N006 0 sky130_fd_pr__nfet_01v8 L=L3 W=W3 nf=1
XM4 N005 vin N006 0 sky130_fd_pr__nfet_01v8 L=L4 W=W4 nf=1
XM1 vop vb2 N005 0 sky130_fd_pr__nfet_01v8 L=L1 W=W1 nf=1
XM2 N001 vb2 N004 0 sky130_fd_pr__nfet_01v8 L=L2 W=W2 nf=1
XM5 N006 vtail 0 0 sky130_fd_pr__nfet_01v8 L=L5 W=W5 nf=1
XM6 vop vb1 N003 vdd sky130_fd_pr__pfet_01v8 L=L6 W=W6 nf=1
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
* OTA009 - Gain-Boosted Cascode (FUNCTIONAL for SKY130)
.param VDD=1.8
.param CL=5p
.param L1=0.8 W1=15
.param L2=0.8 W2=15
.param L3=0.8 W3=30
.param L4=0.8 W4=30
.param L7=1.0 W7=25
.param L8=1.0 W8=20
.param L5=0.8 W5=15
.param L6=1.0 W6=12
Vin vin 0 DC 0.9 AC 1.0
Vb1 vb1 0 DC 0.9
Vb2 vb2 0 DC 0.6
Vb3 vb3 0 DC 1.2
XM1 N005 vin 0 0 sky130_fd_pr__nfet_01v8 L=L1 W=W1 nf=1
XM2 vout N004 N005 0 sky130_fd_pr__nfet_01v8 L=L2 W=W2 nf=1
XM3 N001 N002 vout vdd sky130_fd_pr__pfet_01v8 L=L3 W=W3 nf=1
XM4 vout vb3 N001 vdd sky130_fd_pr__pfet_01v8 L=L4 W=W4 nf=1
XM7 vdd N001 N002 vdd sky130_fd_pr__pfet_01v8 L=L7 W=W7 nf=1
XM8 vdd vb1 N004 N003 sky130_fd_pr__pfet_01v8 L=L8 W=W8 nf=1
XM5 N004 N005 0 0 sky130_fd_pr__nfet_01v8 L=L5 W=W5 nf=1
XM6 N002 vb2 0 0 sky130_fd_pr__nfet_01v8 L=L6 W=W6 nf=1
```
""",
    "ota010": """
```spice
* OTA010 - Folded Cascode Diff PMOS (FUNCTIONAL for SKY130)
.param VDD=1.8
.param CL=10p
.param L1=0.8 W1=30
.param L2=0.8 W2=30
.param L3=0.8 W3=40
.param L4=0.8 W4=45
.param L5=0.8 W5=45
.param L6=0.8 W6=45
.param L7=0.8 W7=45
.param L8=0.8 W8=25
.param L9=1.0 W9=15
.param L10=0.8 W10=25
.param L11=1.0 W11=15
Vinp vinp 0 DC 0.9 AC 0.5
Vinn vinn 0 DC 0.9 AC -0.5
Vb1 vb1 0 DC 0.95
Vb2 vb2 0 DC 0.55
Vb3 vb3 0 DC 0.65
Vb4 vb4 0 DC 1.2
Vb5 vb5 0 DC 1.1
XM1 N001 vinn N005 vdd sky130_fd_pr__pfet_01v8 L=L1 W=W1 nf=1
XM2 N001 vinp N004 vdd sky130_fd_pr__pfet_01v8 L=L2 W=W2 nf=1
XM3 vdd vb1 N001 vdd sky130_fd_pr__pfet_01v8 L=L3 W=W3 nf=1
XM4 vdd vb5 N002 vdd sky130_fd_pr__pfet_01v8 L=L4 W=W4 nf=1
XM5 vdd vb5 N003 vdd sky130_fd_pr__pfet_01v8 L=L5 W=W5 nf=1
XM6 N002 vb4 voutp vdd sky130_fd_pr__pfet_01v8 L=L6 W=W6 nf=1
XM7 N003 vb4 voutn vdd sky130_fd_pr__pfet_01v8 L=L7 W=W7 nf=1
XM8 voutn vb3 N004 0 sky130_fd_pr__nfet_01v8 L=L8 W=W8 nf=1
XM9 N004 vb2 0 0 sky130_fd_pr__nfet_01v8 L=L9 W=W9 nf=1
XM10 voutp vb3 N005 0 sky130_fd_pr__nfet_01v8 L=L10 W=W10 nf=1
XM11 N005 vb2 0 0 sky130_fd_pr__nfet_01v8 L=L11 W=W11 nf=1
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
* OTA012 - Folded Cascode Castail PMOS (FUNCTIONAL for SKY130)
.param VDD=1.8
.param CL=10p
.param L1=0.8 W1=30
.param L2=0.8 W2=30
.param L3=0.8 W3=40
.param L4=0.8 W4=35
.param L5=0.8 W5=40
.param L6=0.8 W6=40
.param L7=0.8 W7=40
.param L8=0.8 W8=24
.param L9=1.0 W9=14
.param L10=0.8 W10=24
.param L11=1.0 W11=14
.param L12=0.8 W12=45
Vinp vinp 0 DC 0.9 AC 0.5
Vinn vinn 0 DC 0.9 AC -0.5
Vb1 vb1 0 DC 0.95
Vb2 vb2 0 DC 0.55
Vb3 vb3 0 DC 0.65
Vb4 vb4 0 DC 1.2
Vb5 vb5 0 DC 1.1
XM1 N004 vinn N006 vdd sky130_fd_pr__pfet_01v8 L=L1 W=W1 nf=1
XM2 N004 vinp N005 vdd sky130_fd_pr__pfet_01v8 L=L2 W=W2 nf=1
XM3 vdd vb1 N002 vdd sky130_fd_pr__pfet_01v8 L=L3 W=W3 nf=1
XM4 vdd N001 N001 vdd sky130_fd_pr__pfet_01v8 L=L4 W=W4 nf=1
XM5 vdd N001 N003 vdd sky130_fd_pr__pfet_01v8 L=L5 W=W5 nf=1
XM6 N001 vb4 vb4 vdd sky130_fd_pr__pfet_01v8 L=L6 W=W6 nf=1
XM7 N003 vb4 vout vdd sky130_fd_pr__pfet_01v8 L=L7 W=W7 nf=1
XM8 vout vb3 N005 0 sky130_fd_pr__nfet_01v8 L=L8 W=W8 nf=1
XM9 N005 vb2 0 0 sky130_fd_pr__nfet_01v8 L=L9 W=W9 nf=1
XM10 vb4 vb3 N006 0 sky130_fd_pr__nfet_01v8 L=L10 W=W10 nf=1
XM11 N006 vb2 0 0 sky130_fd_pr__nfet_01v8 L=L11 W=W11 nf=1
XM12 N002 vb5 N004 vdd sky130_fd_pr__pfet_01v8 L=L12 W=W12 nf=1
```
""",
}


class DummyAdapter(BaseAdapter):
    name = "dummy"

    def predict(self, batch: List[Dict[str, Any]]) -> List[str]:
        outs: List[str] = []
        for item in batch:
            prompt = item.get("prompt", "")
            question = item.get("question", {})
            qid = question.get("id", "")
            
            # Check if this is a design question with verification
            is_design_verification = (
                (question.get("track") == "design" and question.get("verification", {}).get("enabled")) or
                ("design" in qid and "verification" in qid) or
                ("design" in prompt.lower() and ("ota" in prompt.lower() or "blank" in prompt.lower()))
            )
            
            if is_design_verification:
                # Determine OTA type from question ID
                ota_id = None
                for i in range(1, 13):
                    if f"ota{i:03d}" in qid:
                        ota_id = f"ota{i:03d}"
                        break
                
                # Select appropriate template, fallback to ota001
                template = DESIGN_TEMPLATES.get(ota_id, DESIGN_TEMPLATES["ota001"])
                outs.append(template)
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
