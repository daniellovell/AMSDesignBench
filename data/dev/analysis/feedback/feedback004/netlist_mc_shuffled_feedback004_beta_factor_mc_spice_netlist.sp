.subckt opamp in_n in_p out
	* opamp implementation
.ends opamp
XU2 N001 0 S_out opamp Aol=100K GBW=10Meg
R153465675 S_out N001 R
R863607800 N001 S_in R
.backanno
.end

