(define (problem blocksworld-01)
  (:domain blocksworld)
  (:objects a b c)
  (:init
    (clear a) (clear b) (clear c)
    (ontable a) (ontable b) (ontable c)
    (handempty))
  (:goal (and (on a b) (on b c))))
