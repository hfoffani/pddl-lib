;; Courier with parcels: drive one-way tolled roads, load and unload for free.
;; Loading/unloading carry an explicit zero cost: pddlpy's search charges 1
;; for an action without a total-cost effect.
(define (domain courier-parcels)
  (:requirements :strips :typing :action-costs)
  (:types place parcel)
  (:predicates
    (at ?p - place)
    (road ?from - place ?to - place)
    (parcel-at ?x - parcel ?p - place)
    (carrying ?x - parcel))
  (:functions
    (total-cost)
    (toll ?from - place ?to - place))

  (:action drive
    :parameters (?from - place ?to - place)
    :precondition (and (at ?from) (road ?from ?to))
    :effect (and (not (at ?from)) (at ?to)
                 (increase (total-cost) (toll ?from ?to))))

  (:action load
    :parameters (?x - parcel ?p - place)
    :precondition (and (at ?p) (parcel-at ?x ?p))
    :effect (and (carrying ?x) (not (parcel-at ?x ?p))
                 (increase (total-cost) 0)))

  (:action unload
    :parameters (?x - parcel ?p - place)
    :precondition (and (at ?p) (carrying ?x))
    :effect (and (parcel-at ?x ?p) (not (carrying ?x))
                 (increase (total-cost) 0))))
