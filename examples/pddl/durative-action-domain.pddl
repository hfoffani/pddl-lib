;; Durative-action domain (#23): a move with time-tagged conditions and
;; effects ('at start' / 'over all' / 'at end').
(define (domain da)
  (:requirements :strips :typing :durative-actions)
  (:types loc)
  (:predicates
    (at ?l - loc)
    (visited ?l - loc)
    (road ?a - loc ?b - loc))

  (:durative-action go
    :parameters (?from - loc ?to - loc)
    :duration (= ?duration 5)
    :condition (and (at start (at ?from))
                    (over all (road ?from ?to))
                    (at end (road ?from ?to)))
    :effect (and (at start (not (at ?from)))
                 (at end (at ?to))
                 (at end (visited ?to)))))
