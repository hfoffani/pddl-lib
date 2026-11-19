;; The optimality trap (#99): the direct highway depot->town costs 10.
;; The scenic detour depot->riverside->oldbridge->town costs 2+2+3 = 7.
;; A decoy route depot->junction->town costs 5+6 = 11 (looks promising,
;; is not). Cheapest plan: the three-hop detour, total 7.
(define (problem courier-run)
  (:domain courier)
  (:objects depot riverside oldbridge junction town - place)
  (:init
    (at depot)
    (road depot town)        (= (toll depot town) 10)
    (road depot junction)    (= (toll depot junction) 5)
    (road junction town)     (= (toll junction town) 6)
    (road depot riverside)   (= (toll depot riverside) 2)
    (road riverside oldbridge) (= (toll riverside oldbridge) 2)
    (road oldbridge town)    (= (toll oldbridge town) 3)
    (= (total-cost) 0))
  (:goal (at town))
  (:metric minimize (total-cost)))
