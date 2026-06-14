;; Action-costs domain: moving between connected places accrues total-cost
;; equal to the distance travelled. A cost-aware planner should prefer the
;; cheaper multi-hop route over a single expensive hop.
(define (domain travel)
  (:requirements :strips :typing :action-costs)
  (:types place)
  (:predicates
    (at ?p - place)
    (connected ?a - place ?b - place))
  (:functions
    (total-cost)
    (distance ?a - place ?b - place))

  (:action move
    :parameters (?from - place ?to - place)
    :precondition (and (at ?from) (connected ?from ?to))
    :effect (and (not (at ?from))
                 (at ?to)
                 (increase (total-cost) (distance ?from ?to)))))
