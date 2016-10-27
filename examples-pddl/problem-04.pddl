;; a simple DWR problem with 2 robots and 2 locations
(define (problem dwrpb1)
  (:domain dock-worker-robot-pos)

  (:objects
   robr robq - robot
   loc1 loc2 - location
   conta contb - container)

  (:init
   (adjacent loc1 loc2)
   (adjacent loc2 loc1)

   (in conta loc1)
   (in contb loc2)

   (atl robr loc1)
   (atl robq loc2)

   (unloaded robr)
   (unloaded robq)
   )

;; the task is to move all containers to locations l2
;; ca and cc in pile p2, the rest in q2
  (:goal
    (and
        (in contb loc1)
	    (loaded robr conta)
	    )) )
