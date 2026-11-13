/**
 * PDDL grammar for ANTLR v4
 *
 * Zeyn Saigol
 * School of Computer Science
 * University of Birmingham
 *
 * modified for v4 and made it language agnostic by
 * Hernán M. Foffani
 * Now part of the project
 * https://bitbucket.org/hfoffani/pddl-parser
 * 
 * This file carries the same license from the original.
 */

grammar pddl;

// PDDL keywords are case-insensitive (#20 / #36). caseInsensitive makes
// literal keyword tokens match any case while preserving the original
// text of identifiers (object/predicate names stay case-sensitive).
options { caseInsensitive = true; }

tokens {
    DOMAIN,
    DOMAIN_NAME,
    REQUIREMENTS,
    TYPES,
    EITHER_TYPE,
    CONSTANTS,
    FUNCTIONS,
    PREDICATES,
    ACTION,
    DURATIVE_ACTION,
    PROBLEM,
    PROBLEM_NAME,
    PROBLEM_DOMAIN,
    OBJECTS,
    INIT,
    FUNC_HEAD,
    PRECONDITION,
    EFFECT,
    AND_GD,
    OR_GD,
	NOT_GD,
	IMPLY_GD,
	EXISTS_GD,
	FORALL_GD,
	COMPARISON_GD,
	AND_EFFECT,
	FORALL_EFFECT,
	WHEN_EFFECT,
	ASSIGN_EFFECT,
	NOT_EFFECT,
	PRED_HEAD,
	GOAL,
	BINARY_OP,
	UNARY_MINUS,
	INIT_EQ,
	INIT_AT,
	NOT_PRED_INIT,
	PRED_INST,
	PROBLEM_CONSTRAINT,
	PROBLEM_METRIC
}


/************* Start of grammar *******************/

pddlDoc : domain | problem;

/************* DOMAINS ****************************/

domain
    // One alternative: two that differ only in where the optional
    // contextDef goes are identical without it, and ANTLR then looks
    // ahead to the end of the file to choose.
    : '(' 'define' domainName
      ( requireDef contextDef? | contextDef requireDef? )?
      typesDef?
      constantsDef?
      predicatesDef?
      functionsDef?
      constraints?
      structureDef*
      ')'
    ;

domainName
    : '(' 'domain' name ')'
    ;

contextDef
	: '(' ':context' namespaceBinding+ ')'
	;


namespaceBinding
	: name '-' URI
	;

requireDef
	: '(' ':requirements' REQUIRE_KEY+ ')'
	;

typesDef
	: '(' ':types' typedNameList ')'
	;

// If have any typed names, they must come FIRST!
typedNameList
    : (name* | singleTypeNameList+ name*)
    ;

singleTypeNameList
    : (name+ '-' t=r_type)
	;

r_type
	: ( '(' 'either' primType+ ')' )
	| primType
	;

primType : name ;

functionsDef
	: '(' ':functions' functionList ')'
	;

functionList
	: (atomicFunctionSkeleton+ ('-' functionType)? )*
	;

atomicFunctionSkeleton
	: '(' functionSymbol typedVariableList ')'
	;

functionSymbol : symbol ;

functionType : 'number' ; // Currently in PDDL only numeric functions are allowed

constantsDef
	: '(' ':constants' typedNameList ')'
	;

predicatesDef
	: '(' ':predicates' atomicFormulaSkeleton+ ')'
	;

atomicFormulaSkeleton
	: '(' predicate typedVariableList ')'
	;

predicate : symbol ;

// If have any typed variables, they must come FIRST!
typedVariableList
    : (VARIABLE* | singleTypeVarList+ VARIABLE*)
    ;

singleTypeVarList
    : (VARIABLE+ '-' t=r_type)
    ;

constraints
	: '(' ':constraints' conGD ')'
	;

structureDef
	: actionDef
	| durativeActionDef
	| derivedDef
	;


/************* ACTIONS ****************************/

actionDef
	: '(' ':action' actionSymbol
	      ':parameters' '(' typedVariableList ')'
           actionDefBody ')'
    ;

actionSymbol : symbol ;


// Should allow preGD instead of goalDesc for preconditions -
// but I can't get the LL(*) parsing to work
// This means 'preference' preconditions cannot be used
actionDefBody
	: ( ':precondition' (('(' ')') | precondition))?
	  ( ':effect' (('(' ')') | effect))?
	;

// to ease Listener implementation
precondition
    : goalDesc
    ;

//preGD
//	: prefGD
//	| '(' 'and' preGD* ')'
//	| '(' 'forall' '(' typedVariableList ')' preGD ')'
//	;
//
//prefGD
//	: '(' 'preference' name? goalDesc ')'
//	| goalDesc
//	;

goalDesc
	: atomicTermFormula
	| '(' 'and' goalDesc* ')'
	| '(' 'or' goalDesc* ')'
	| '(' 'not' goalDesc ')'
	| '(' 'imply' goalDesc goalDesc ')'
	| '(' 'exists' '(' typedVariableList ')' goalDesc ')'
	| '(' 'forall' '(' typedVariableList ')' goalDesc ')'
	| '(' '=' term term ')'
    | fComp
    ;

fComp
	: '(' binaryComp fExp fExp ')'
	;

atomicTermFormula
	: '(' predicate term* ')'
	;

term : name | VARIABLE ;

/************* DURATIVE ACTIONS ****************************/

durativeActionDef
	: '(' ':durative-action' actionSymbol
	      ':parameters' '(' typedVariableList ')'
           daDefBody ')'
    ;

daDefBody
	: ':duration' durationConstraint
	  ':condition' (('(' ')') | daGD)
	  ':effect' (('(' ')') | daEffect)
	;

daGD
	: prefTimedGD
	| '(' 'and' daGD* ')'
	| '(' 'forall' '(' typedVariableList ')' daGD ')'
	;

prefTimedGD
	: timedGD
	| '(' 'preference' name? timedGD ')'
	;

timedGD
	: '(' 'at' timeSpecifier goalDesc ')'
	| '(' 'over' interval goalDesc ')'
	;

timeSpecifier : 'start' | 'end' ;
interval : 'all' ;

/************* DERIVED DEFINITIONS ****************************/

derivedDef
	: '(' ':derived' atomicFormulaSkeleton goalDesc ')'
	;

/************* EXPRESSIONS ****************************/

fExp
	: NUMBER
	| '(' binaryOp fExp fExp2 ')' 
	| '(' '-' fExp ')' 
	| fHead
	;

// This is purely a workaround for an ANTLR bug in tree construction
// http://www.antlr.org/wiki/display/ANTLR3/multiple+occurences+of+a+token+mix+up+the+list+management+in+tree+rewrites
fExp2 : fExp ;

fHead
	: '(' functionSymbol term* ')' 
	| functionSymbol 
	;

effect
	: '(' 'and' cEffect* ')' 
	| cEffect
	;

cEffect
	: '(' 'forall' '(' typedVariableList ')' effect ')'
	| '(' 'when' goalDesc condEffect ')'
	| pEffect
	;

pEffect
	: '(' assignOp fHead fExp ')'
	| '(' 'not' atomicTermFormula ')'
	| atomicTermFormula
	;


// TODO: why is this different from the "and cEffect" above? Does it matter?
condEffect
	: '(' 'and' pEffect* ')' 
	| pEffect
	;

// TODO: should these be uppercase & lexer section?
binaryOp : '*' | '+' | '-' | '/' ;

binaryComp : '>' | '<' | '=' | '>=' | '<=' ;

assignOp : 'assign' | 'scale-up' | 'scale-down' | 'increase' | 'decrease' ;


/************* DURATIONS  ****************************/

durationConstraint
	: '(' 'and' simpleDurationConstraint+ ')'
	| '(' ')'
	| simpleDurationConstraint
	;

simpleDurationConstraint
	: '(' durOp '?duration' durValue ')'
	| '(' 'at' timeSpecifier simpleDurationConstraint ')'
	;

durOp : '<=' | '>=' | '=' ;

durValue : NUMBER | fExp ;

daEffect
	: '(' 'and' daEffect* ')'
	| timedEffect
	| '(' 'forall' '(' typedVariableList ')' daEffect ')'
	| '(' 'when' daGD timedEffect ')'
	| '(' assignOp fHead fExpDA ')'
	;

timedEffect
	: '(' 'at' timeSpecifier cEffect ')'
	| '(' 'at' timeSpecifier fAssignDA ')'
	| '(' assignOpT fHead fExp ')' /* fExpT in BNF but not making sense */
	;

fAssignDA
	: '(' assignOp fHead fExpDA ')'
	;

fExpDA
	: '(' ((binaryOp fExpDA fExpDA) | ('-' fExpDA)) ')'
	| '?duration'
	| fExp
	;

assignOpT : 'increase' | 'decrease' ;

/*
 * We should have fExpT according to:
 * http://www.plg.inf.uc3m.es/ipc2011-deterministic/attachments/OtherContributions/kovacs-pddl-3.1-2011.pdf

fExpT
	: '(*' fExp #t ')'
	| '(*' #t fExp ')'
	| #t
	;
 */

/************* PROBLEMS ****************************/

problem
    // One alternative, as in domain: no lookahead to the end of the file.
    : '(' 'define' problemDecl
      ( problemDomain requireDef? contextDef? | contextDef problemDomain requireDef? )
      objectDecl?
      init
      goal
      probConstraints?
      metricSpec?
      // lengthSpec? This is not defined anywhere in the BNF spec
      ')'
    ;

problemDecl
    : '(' 'problem' name ')'
    ;

problemDomain
	: '(' ':domain' name ')'
	;

objectDecl
	: '(' ':objects' typedNameList ')'
	;

init
	: '(' ':init' initEl* ')'
	;

initEl
	: nameLiteral
	| '(' '=' fHead NUMBER ')'         
	| '(' 'at' NUMBER nameLiteral ')'
	;

nameLiteral
	: atomicNameFormula
	| '(' 'not' atomicNameFormula ')' 
	;

atomicNameFormula
	: '(' predicate name* ')' 
	;

// Should allow preGD instead of goalDesc -
// but I can't get the LL(*) parsing to work
// This means 'preference' preconditions cannot be used
//goal : '(' ':goal' preGD ')'  
goal
    : '(' ':goal' preGD ')'
    ;

// A goal with PDDL 3.0 preferences (#201). 'and' / 'forall' come first, so
// a plain goal is read through them (ANTLR picks the first alternative of
// an ambiguity); the listener rebuilds the hard goal and the preferences.
preGD
	: '(' 'and' preGD* ')'
	| '(' 'forall' '(' typedVariableList ')' preGD ')'
	| '(' 'preference' name? goalDesc ')'
	| goalDesc
	;

probConstraints
	: '(' ':constraints'  prefConGD ')'
	;

prefConGD
	: '(' 'and' prefConGD* ')'
	| '(' 'forall' '(' typedVariableList ')' prefConGD ')'
	| '(' 'preference' name? conGD ')'
	| conGD
	;

metricSpec
	: '(' ':metric' optimization metricFExp ')'
	;

optimization : 'minimize' | 'maximize' ;

metricFExp
	: '(' binaryOp metricFExp metricFExp ')'
	| '(' ('+'|'*'|'/') metricFExp metricFExp+ ')'
	| '(' '-' metricFExp ')'
	| NUMBER
	| '(' functionSymbol name* ')'
	| functionSymbol
	| 'total-time'
	| '(' 'total-time' ')'
	| '(' 'is-violated' name ')'
	;

/************* CONSTRAINTS ****************************/

conGD
	: '(' 'and' conGD* ')'
	| '(' 'forall' '(' typedVariableList ')' conGD ')'
	| '(' 'at' 'end' goalDesc ')'
	| '(' 'always' goalDesc ')'
	| '(' 'sometime' goalDesc ')'
 	| '(' 'within' NUMBER goalDesc ')'
	| '(' 'at-most-once' goalDesc ')'
	| '(' 'sometime-after' goalDesc goalDesc ')'
	| '(' 'sometime-before' goalDesc goalDesc ')'
	| '(' 'always-within' NUMBER goalDesc goalDesc ')'
	| '(' 'hold-during' NUMBER NUMBER goalDesc ')'
	| '(' 'hold-after' NUMBER goalDesc ')'
	;



/************* LEXER ****************************/


REQUIRE_KEY
    : ':strips'
    | ':typing'
    | ':negative-preconditions'
    | ':disjunctive-preconditions'
    | ':equality'
    | ':existential-preconditions'
    | ':universal-preconditions'
    | ':quantified-preconditions'
    | ':conditional-effects'
    | ':fluents'
    | ':numeric-fluents'
    | ':action-costs'
    | ':adl'
    | ':durative-actions'
    | ':derived-predicates'
    | ':duration-inequalities'
    | ':timed-initial-literals'
    | ':preferences'
    | ':constraints'
    | ':semantics'
    ;

/*
 * allowing keywords as identifier where allowed
 * may need more to specify
 */
// A name: objects, constants, types, arguments (#163). PDDL names are any
// letter-led identifier, so a word the lexer reads as a keyword token is a
// name here too.
name
	: symbol
	| 'all' | 'always' | 'always-within' | 'and' | 'assign' | 'at-most-once'
	| 'decrease' | 'define' | 'domain' | 'either' | 'end' | 'exists'
	| 'forall' | 'hold-after' | 'hold-during' | 'imply' | 'increase'
	| 'is-violated' | 'maximize' | 'minimize' | 'not' | 'number' | 'or'
	| 'preference' | 'problem' | 'scale-down' | 'scale-up' | 'sometime'
	| 'sometime-after' | 'sometime-before' | 'start' | 'total-time' | 'when'
	| 'within'
	;

// Predicate, function and action names: keywords stay out, so (and),
// (not ...) and (or ...) keep one reading.
symbol
	: NAME
	| 'at'
	| 'over'
	;

NAME:    LETTER ANY_CHAR* ;

URI:	 LETTER ~(' ' | '\r' | '\n' | '\t' | '(' | ')')* ;

// caseInsensitive matching folds A-Z into a-z; the original text is
// preserved, so identifiers remain case-sensitive in getText().
fragment LETTER:	'a'..'z';

fragment ANY_CHAR: LETTER | '0'..'9' | '-' | '_';

VARIABLE : '?' LETTER ANY_CHAR* ;

NUMBER : DIGIT+ ('.' DIGIT+)? ;

fragment DIGIT: '0'..'9';

LINE_COMMENT
    : ';' ~('\n'|'\r')* ('\r'? '\n' | EOF) -> skip
    ;

WHITESPACE
    :   (   ' '
        |   '\t'
        |   '\r'
        |   '\n'
        )+
        -> skip
    ;
