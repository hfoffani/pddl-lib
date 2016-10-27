;; The D1S1 domain, STRIPS version (adapted from the SGP distribution).

(define (domain D1S1)
  (:requirements :strips)
  (:predicates
   (I0) (I1) (I2)
   (G1) (G2))

  (:action A2
	   :parameters () 
	   :precondition (I2) 
	   :effect (and (not (I1)) (G2)))

  (:action A1
	   :parameters () 
	   :precondition (and (I1) (not (I0)))
	   :effect (and (not (I0)) (G1)))
  )
