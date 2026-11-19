;; 10 planes, 4 days, 3 airports. Optimum: 2 crew-days (day2 at madrid,
;; day3 at paris). Greedy trap: day1 at madrid covers the most planes (6)
;; but leaves {p4 p5 p9 p10}, which no single crew-day covers -> 3 days.
(define (problem maintenance-10)
  (:domain maintenance)
  (:objects p1 p2 p3 p4 p5 p6 p7 p8 p9 p10 - plane
            day1 day2 day3 day4 - day
            madrid paris rome - airport)
  (:init
    (today day1) (today day2) (today day3) (today day4)
    ;;            day1          day2          day3          day4
    (at p1 day1 madrid) (at p1 day2 madrid) (at p1 day3 madrid) (at p1 day4 madrid)
    (at p2 day1 madrid) (at p2 day2 madrid) (at p2 day3 madrid) (at p2 day4 paris)
    (at p3 day1 madrid) (at p3 day2 madrid) (at p3 day3 rome)   (at p3 day4 rome)
    (at p4 day1 paris)  (at p4 day2 madrid) (at p4 day3 rome)   (at p4 day4 madrid)
    (at p5 day1 paris)  (at p5 day2 madrid) (at p5 day3 rome)   (at p5 day4 paris)
    (at p6 day1 madrid) (at p6 day2 paris)  (at p6 day3 paris)  (at p6 day4 rome)
    (at p7 day1 madrid) (at p7 day2 paris)  (at p7 day3 paris)  (at p7 day4 madrid)
    (at p8 day1 madrid) (at p8 day2 rome)   (at p8 day3 paris)  (at p8 day4 paris)
    (at p9 day1 rome)   (at p9 day2 rome)   (at p9 day3 paris)  (at p9 day4 rome)
    (at p10 day1 rome)  (at p10 day2 rome)  (at p10 day3 paris) (at p10 day4 madrid))
  (:goal (and (done p1) (done p2) (done p3) (done p4) (done p5)
              (done p6) (done p7) (done p8) (done p9) (done p10))))
