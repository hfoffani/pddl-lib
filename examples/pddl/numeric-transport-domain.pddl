;; Minimal numeric-fluents domain: a vehicle drives between locations,
;; consuming fuel. Exercises :functions, a numeric precondition (>=) and a
;; numeric effect (decrease).
(define (domain numeric-transport)
  (:requirements :strips :typing :fluents)
  (:types location vehicle)
  (:predicates
    (at ?v - vehicle ?l - location)
    (road ?from - location ?to - location))
  (:functions
    (fuel ?v - vehicle)
    (fuel-cost ?from - location ?to - location))

  (:action drive
    :parameters (?v - vehicle ?from - location ?to - location)
    :precondition (and (at ?v ?from)
                       (road ?from ?to)
                       (>= (fuel ?v) (fuel-cost ?from ?to)))
    :effect (and (not (at ?v ?from))
                 (at ?v ?to)
                 (decrease (fuel ?v) (fuel-cost ?from ?to)))))
