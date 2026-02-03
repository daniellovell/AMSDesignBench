.subckt opamp in_n in_p out
	* opamp implementation
.ends opamp
XU1 N001 S_in S_out opamp Aol=100K GBW=10Meg
R925830092 0 N001 R
R300847582 S_out N001 R
.backanno
.end

