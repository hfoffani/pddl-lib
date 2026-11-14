;; 3 cities (each: an airport + a downtown office), 3 trucks, 1 airplane,
;; 3 packages that all need truck + plane + truck. 4 packages: ~20 s optimal
;; in pddlpy, 5: > 2 min.
(define (problem logistics-3-3)
  (:domain logistics)
  (:objects madrid paris rome - city
            mad-airport cdg-airport fco-airport - airport
            mad-office paris-office rome-office - location
            mad-truck paris-truck rome-truck - truck
            plane - airplane
            p1 p2 p3 - package)
  (:init
    (in-city mad-airport madrid) (in-city mad-office madrid)
    (in-city cdg-airport paris)  (in-city paris-office paris)
    (in-city fco-airport rome)   (in-city rome-office rome)
    (at mad-truck mad-office) (at paris-truck cdg-airport) (at rome-truck rome-office)
    (at plane fco-airport)
    (at p1 mad-office) (at p2 paris-office) (at p3 cdg-airport))
  (:goal (and (at p1 rome-office) (at p2 mad-office) (at p3 rome-office))))
