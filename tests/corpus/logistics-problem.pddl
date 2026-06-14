(define (problem logistics-01)
  (:domain logistics)
  (:objects
    apn1 - airplane
    apt1 apt2 - airport
    pos1 pos2 - location
    cit1 cit2 - city
    tru1 tru2 - truck
    obj1 obj2 - package)
  (:init
    (in-city pos1 cit1) (in-city apt1 cit1)
    (in-city pos2 cit2) (in-city apt2 cit2)
    (at apn1 apt2)
    (at tru1 pos1) (at obj1 pos1)
    (at tru2 pos2) (at obj2 pos2))
  (:goal (and (at obj1 apt1) (at obj2 pos1))))
