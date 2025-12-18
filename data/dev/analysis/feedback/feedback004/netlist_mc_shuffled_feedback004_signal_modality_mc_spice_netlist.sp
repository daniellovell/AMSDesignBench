.subckt opamp in_n in_p out
	* opamp implementation
.ends opamp
XU2 N001 0 S_out opamp Aol=100K GBW=10Meg
R556569669 S_out N001 R
R426812734 N001 S_in R
.backanno
.end

