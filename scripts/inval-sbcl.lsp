;; Build a standalone INVAL executable with SBCL (#153).
;;
;; INVAL's inval-main.lsp is written for ECL: it reads its arguments with
;; ext:command-args and validates on load. This shim provides that function,
;; preloads INVAL into an SBCL core, and makes loading inval-main.lsp the
;; executable's entry point.
;;
;;   cd INVAL && sbcl --non-interactive --load inval-sbcl.lsp
;;   ./inval DOMAIN PROBLEM PLAN
(defpackage :ext (:use :cl) (:export #:command-args))
(defun ext:command-args () sb-ext:*posix-argv*)
(load "inval.lsp")
(load "vis.lsp")
(defparameter *inval-main* (merge-pathnames "inval-main.lsp" *load-truename*))
(sb-ext:save-lisp-and-die
 "inval"
 :executable t
 :save-runtime-options t
 :toplevel (lambda () (load *inval-main*) (sb-ext:exit)))
