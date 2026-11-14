;; After IPC-2014 Maintenance (aircraft maintenance scheduling): on a day
;; the crew works at one airport and services every plane parked there.
(define (domain maintenance)
  (:requirements :adl :typing :conditional-effects)
  (:types plane day airport)
  (:predicates (done ?p - plane)
               (today ?d - day)
               (at ?p - plane ?d - day ?c - airport))

  (:action workat
    :parameters (?day - day ?airport - airport)
    :precondition (today ?day)
    :effect (and (not (today ?day))
                 (forall (?plane - plane)
                   (when (at ?plane ?day ?airport) (done ?plane))))))
