;; The classic "briefcase world" (Pednault) — the canonical showcase for
;; conditional and universal effects (:conditional-effects). Moving the
;; briefcase relocates every item that happens to be inside it.
(define (domain briefcase)
  (:requirements :typing :negative-preconditions :conditional-effects)
  (:types item location)
  (:predicates
    (at ?i - item ?l - location)   ; item ?i is at location ?l
    (in ?i - item)                 ; item ?i is inside the briefcase
    (b-at ?l - location))          ; the briefcase is at location ?l
  (:action move
    :parameters (?from - location ?to - location)
    :precondition (b-at ?from)
    :effect (and
      (b-at ?to)
      (not (b-at ?from))
      (forall (?i - item)
        (when (in ?i)
          (and (at ?i ?to) (not (at ?i ?from)))))))
  (:action put-in
    :parameters (?i - item ?l - location)
    :precondition (and (at ?i ?l) (b-at ?l))
    :effect (in ?i))
  (:action take-out
    :parameters (?i - item)
    :precondition (in ?i)
    :effect (not (in ?i))))
