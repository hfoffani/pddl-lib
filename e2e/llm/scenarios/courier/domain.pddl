;; Courier domain for docs/llm-interaction.md (#99): moving between connected
;; places accrues total-cost equal to the road toll. Deliberately tiny -- the
;; point of the example is cost-OPTIMAL routing, where greedy answers fail.
(define (domain courier)
  (:requirements :strips :typing :action-costs)
  (:types place)
  (:predicates
    (at ?p - place)
    (road ?from - place ?to - place))
  (:functions
    (total-cost)
    (toll ?from - place ?to - place))

  (:action drive
    :parameters (?from - place ?to - place)
    :precondition (and (at ?from) (road ?from ?to))
    :effect (and (not (at ?from))
                 (at ?to)
                 (increase (total-cost) (toll ?from ?to)))))
