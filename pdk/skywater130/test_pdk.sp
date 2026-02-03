* SKY130 PDK Test - Basic NMOS Gm/ID sweep
* This verifies that the official SKY130 models work correctly with ngspice

* Include global parameters first
.include models/all.spice

* Then include corner-specific models
.lib models/sky130.lib.spice tt

* Supply
Vdd vdd 0 DC 1.8
Vss vss 0 DC 0

* Test NMOS device
XM1 vdd vgs vss vss sky130_fd_pr__nfet_01v8 L=0.5u W=1u nf=1

* Gate voltage sweep
Vgs vgs 0 DC 0.6

* DC operating point and sweep
.control
dc Vgs 0 1.8 0.01

* Calculate gm/Id
let gm = @m.xm1.msky130_fd_pr__nfet_01v8[gm]
let id = abs(@m.xm1.msky130_fd_pr__nfet_01v8[id])
let gmid = gm/id

* Print results
print vgs id gm gmid > test_pdk_results.txt
plot gmid vs vgs
quit
.endc

.end

