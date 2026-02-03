.subckt opamp in_n in_p out
	* opamp implementation
.ends opamp
XU2 N001 0 S_out opamp Aol=100K GBW=10Meg
R612569032 S_out N001 R
R491424436 N001 S_in R
.backanno
.end

