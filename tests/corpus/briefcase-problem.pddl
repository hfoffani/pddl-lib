;; Carry o1 to the office in the briefcase while o2 stays home.
;; Optimal plan: (put-in o1 home) (move home office).
(define (problem briefcase-01)
  (:domain briefcase)
  (:objects home office - location
            o1 o2 - item)
  (:init
    (b-at home)
    (at o1 home)
    (at o2 home))
  (:goal (and
    (b-at office)
    (at o1 office)
    (at o2 home))))
