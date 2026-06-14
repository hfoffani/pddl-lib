(define (problem numeric-transport-01)
  (:domain numeric-transport)
  (:objects
    truck - vehicle
    a b c - location)
  (:init
    (at truck a)
    (road a b) (road b c)
    (= (fuel truck) 100)
    (= (fuel-cost a b) 30)
    (= (fuel-cost b c) 40))
  (:goal (at truck c)))
