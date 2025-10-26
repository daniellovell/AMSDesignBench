subckt opamp in_n in_p out
	* opamp implementation
ends opamp
XU2 S_in 0 S_out opamp Aol=100K GBW=10Meg
R1 S_out S_in R
.backanno
.end

