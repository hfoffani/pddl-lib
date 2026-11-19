;; 8 blocks, three stacks -> two towers. Parts of the start can stay put
;; (a stays on the table, d already sits on b), so "unstack everything,
;; then rebuild" works but is not the fewest moves.
(define (problem blocks-8)
  (:domain blocks)
  (:objects a b c d e f g h - block)
  (:init (handempty)
    (ontable a) (on c a) (on e c) (on g e) (clear g)
    (ontable b) (on d b) (clear d)
    (ontable f) (on h f) (clear h))
  (:goal (and (on b a) (on c b) (on d c)
              (on g h) (on f g) (on e f))))
