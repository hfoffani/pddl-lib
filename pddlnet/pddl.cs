using System.Collections.Generic;
using System.IO;
using Antlr4.Runtime;

namespace PDDLNET {

internal class Atom {
}

internal class Scope {
}

internal class Obj {
}

internal class Operator {
}

internal class DomainListener : pddlBaseListener {
    HashSet<object> objects = new HashSet<object>();
    HashSet<object> operators = new HashSet<object>();
    List<object> scopes = new List<object>();
    List<object> negativescopes = new List<object>();
    bool typesdef = false;


    public override void EnterActionDef(pddlParser.ActionDefContext ctx) {
        /*
        opname = ctx.actionSymbol().getText()
        opvars = {}
        self.scopes.append(Operator(opname))
        */
    }

    public override void ExitActionDef(pddlParser.ActionDefContext ctx) {
        /*
        action = self.scopes.pop()
        self.operators[action.operator_name] = action
        */
    }

    public override void EnterPredicatesDef(pddlParser.PredicatesDefContext ctx) {
        /*
        self.scopes.append(Operator(None))
        */
    }

    public override void ExitPredicatesDef(pddlParser.PredicatesDefContext ctx) {
        /*
        dummyop = self.scopes.pop()
        */
    }

    public override void EnterTypesDef(pddlParser.TypesDefContext ctx) {
        /*
        self.scopes.append(Obj())
        */
    }

    public override void ExitTypesDef(pddlParser.TypesDefContext ctx) {
        /*
        self.typesdef = True
        self.scopes.pop()
        */
    }

    public override void EnterTypedVariableList(pddlParser.TypedVariableListContext ctx) {
        /*
        # print("-> tvar")
        for v in ctx.VARIABLE():
            vname = v.getText()
            self.scopes[-1].variable_list[v.getText()] = None
        for vs in ctx.singleTypeVarList():
            t = vs.r_type().getText()
            for v in vs.VARIABLE():
                vname = v.getText()
                self.scopes[-1].variable_list[vname] = t
        */
    }

    public override void EnterAtomicTermFormula(pddlParser.AtomicTermFormulaContext ctx) {
        /*
        # print("-> terf")
        neg = self.negativescopes[-1]
        pred = []
        for c in ctx.getChildren():
            n = c.getText()
            if n == '(' or n == ')':
                continue
            pred.append(n)
        scope = self.scopes[-1]
        if not neg:
            scope.addatom(Atom(pred))
        else:
            scope.addnegatom(Atom(pred))

        */
    }

    public override void EnterPrecondition(pddlParser.PreconditionContext ctx) {
        /*
        self.scopes.append(Scope())
        */
    }

    public override void ExitPrecondition(pddlParser.PreconditionContext ctx) {
        /*
        scope = self.scopes.pop()
        self.scopes[-1].precondition_pos = set( scope.atoms )
        self.scopes[-1].precondition_neg = set( scope.negatoms )
        */
    }

    public override void EnterEffect(pddlParser.EffectContext ctx) {
        /*
        self.scopes.append(Scope())
        */
    }

    public override void ExitEffect(pddlParser.EffectContext ctx) {
        /*
        scope = self.scopes.pop()
        self.scopes[-1].effect_pos = set( scope.atoms )
        self.scopes[-1].effect_neg = set( scope.negatoms )
        */
    }

    public override void EnterGoalDesc(pddlParser.GoalDescContext ctx) {
        /*
        negscope = False
        for c in ctx.getChildren():
            if c.getText() == 'not':
                negscope = True
                break
        self.negativescopes.append(negscope)
        */
    }

    public override void ExitGoalDesc(pddlParser.GoalDescContext ctx) {
        /*
        self.negativescopes.pop()
        */
    }

    public override void EnterPEffect(pddlParser.PEffectContext ctx) {
        /*
        negscope = False
        for c in ctx.getChildren():
            if c.getText() == 'not':
                negscope = True
                break
        self.negativescopes.append(negscope)
        */
    }

    public override void ExitPEffect(pddlParser.PEffectContext ctx) {
        /*
        self.negativescopes.pop()
        */
    }

    public override void EnterTypedNameList(pddlParser.TypedNameListContext ctx) {
        /*
        # print("-> tnam")
        for v in ctx.NAME():
            vname = v.getText()
            self.scopes[-1].variable_list[v.getText()] = None
        for vs in ctx.singleTypeNameList():
            t = vs.r_type().getText()
            for v in vs.NAME():
                vname = v.getText()
                self.scopes[-1].variable_list[vname] = t
        */
    }

    public override void EnterConstantsDef(pddlParser.ConstantsDefContext ctx) {
        /*
        self.scopes.append(Obj())
        */
    }

    public override void ExitConstantsDef(pddlParser.ConstantsDefContext ctx) {
        /*
        scope = self.scopes.pop()
        self.objects = scope.variable_list
        */
    }

    public override void ExitDomain(pddlParser.DomainContext ctx) {
        /*
        if not self.objects and not self.typesdef:
            vs = set()
            for opn, oper in self.operators.items():
                alls = oper.precondition_pos | oper.precondition_neg | oper.effect_pos | oper.      effect_neg
                for a in alls:
                    for s in a.predicate:
                        if s[0] != '?':
                            vs.add( (s, None) )
            self.objects = dict( vs)
        */
    }

}

internal class ProblemListener : pddlBaseListener {
}

public class DomainProblem {

    private DomainListener domain;
    private ProblemListener problem;
    
    public DomainProblem() {
    }

    public DomainProblem(string domainfile, string problemfile) : this() {
        using (var domstream = new StreamReader(domainfile)) {
            var inp = new Antlr4.Runtime.AntlrInputStream(domstream);
            var lexer = new pddlLexer(inp);
            var stream = new Antlr4.Runtime.CommonTokenStream(lexer);
            var parser = new pddlParser(stream);
            var tree = parser.domain();
            this.domain = new DomainListener();
            var walker = new Antlr4.Runtime.Tree.ParseTreeWalker();
            walker.Walk(this.domain, tree);
        }

        using (var probstream  = new StreamReader(problemfile)) {
            var inp = new Antlr4.Runtime.AntlrInputStream(probstream);
            var lexer = new pddlLexer(inp);
            var stream = new Antlr4.Runtime.CommonTokenStream(lexer);
            var parser = new pddlParser(stream);
            var tree = parser.problem();
            this.problem = new ProblemListener();
            var walker = new Antlr4.Runtime.Tree.ParseTreeWalker();
            walker.Walk(this.problem, tree);
        }
    }

}

}

