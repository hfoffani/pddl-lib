using System.Collections.Generic;
using System.IO;
using System.Linq;

using Antlr4.Runtime;

namespace PDDLNET {

internal class ElementCollection<T> : IReadOnlyCollection<T> {

    private List<T> _pred = new List<T>();
    int _hash = 0;

    public ElementCollection() {
    }

    public ElementCollection(IEnumerable<T> predicate) {
        _pred.AddRange(predicate);
        for (int i = 0; i < _pred.Count; i++) {
            _hash ^= _pred[i].GetHashCode() + i;
        }
    }

    public int Count {
        get { return _pred.Count; }
    }

    public IEnumerator<T> GetEnumerator() {
        return _pred.GetEnumerator();
    }

    System.Collections.IEnumerator System.Collections.IEnumerable.GetEnumerator() {
        return _pred.GetEnumerator();
    }

    public override bool Equals(object obj) {
        if (obj == null)
            return false;
        var other = obj as ElementCollection<T>;
        if (other == null)
            return false;
        return this.GetHashCode() == other.GetHashCode();
    }
    public override int GetHashCode() {
        return _hash;
    }

    public override string ToString() {
        var s = new System.Text.StringBuilder();
        s.Append("(");
        foreach (var it in this._pred) {
            s.Append(it.ToString());
            s.Append(", ");
        }
        s.Append(")");
        return s.ToString();
    }
}


internal class Atom {
    // should be a tuple. or a hashable immutable object.
    public ElementCollection<string> predicate = new ElementCollection<string>();

    internal Atom(IList<string> predicate) {
        this.predicate = new ElementCollection<string>( predicate);
    }
}

interface IScopeItem {
}

internal class Scope : IScopeItem {
    public HashSet<object> atoms = new HashSet<object>();
    public HashSet<object> negatoms = new HashSet<object>();

    public void addatom(Atom atom) {
        atoms.UnionWith(atom.predicate);
    }

    public void addnegatom(Atom atom) {
        negatoms.UnionWith(atom.predicate);
    }
}

internal class Obj : IScopeItem {
    public Dictionary<string, object> variable_list = null;
}

internal class Operator : IScopeItem {
    public string operator_name = "";
    public HashSet<object> precondition_pos = null;
    public HashSet<object> precondition_neg = null;
    public HashSet<object> effect_pos = null;
    public HashSet<object> effect_neg = null;
    public Dictionary<string, object> variable_list = null;

    public Operator(string name) {
        this.operator_name = name;
    }
}

internal class DomainListener : pddlBaseListener {
    internal Dictionary<string, object> objects = new Dictionary<string, object>();
    internal Dictionary<string, object> operators = new Dictionary<string, object>();
    Stack<IScopeItem> scopes = new Stack<IScopeItem>();
    Stack<bool> negativescopes = new Stack<bool>();
    bool typesdef = false;


    public override void EnterActionDef(pddlParser.ActionDefContext ctx) {
        /*
        opname = ctx.actionSymbol().getText()
        opvars = {}
        self.scopes.append(Operator(opname))
        */
        var opname = ctx.actionSymbol().GetText();
        this.scopes.Push(new Operator(opname) );
    }

    public override void ExitActionDef(pddlParser.ActionDefContext ctx) {
        /*
        action = self.scopes.pop()
        self.operators[action.operator_name] = action
        */
        var action = (Operator)this.scopes.Pop();
        this.operators.Add(action.operator_name, action);
    }

    public override void EnterPredicatesDef(pddlParser.PredicatesDefContext ctx) {
        /*
        self.scopes.append(Operator(None))
        */
        this.scopes.Push(new Operator( null) );
    }

    public override void ExitPredicatesDef(pddlParser.PredicatesDefContext ctx) {
        /*
        dummyop = self.scopes.pop()
        */
        this.scopes.Pop();
    }

    public override void EnterTypesDef(pddlParser.TypesDefContext ctx) {
        /*
        self.scopes.append(Obj())
        */
        this.scopes.Push(new Obj() );
    }

    public override void ExitTypesDef(pddlParser.TypesDefContext ctx) {
        /*
        self.typesdef = True
        self.scopes.pop()
        */
        this.typesdef = true;
        this.scopes.Pop();
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
        System.Console.WriteLine("-> tvar");
        foreach (var v in ctx.VARIABLE()) {
            var vname = v.GetText();
            var op = (Operator)this.scopes.Peek();
            op.variable_list.Add(vname, null);
        }
        foreach (var vs in ctx.singleTypeVarList()) {
            var t = vs.r_type().GetText();
            foreach (var v in vs.VARIABLE()) {
                var vname = v.GetText();
                var op = (Operator)this.scopes.Peek();
                op.variable_list.Add(vname, t);
            }
        }
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
        System.Console.WriteLine("-> terf");
        var neg = this.negativescopes.Peek();
        var pred = new List<string>();
        var nchilds = 5 ; // TO DO. MAL OJO. va ctx.getChildCount()
        for (int i = 0; i < nchilds; i++) {
            var c = ctx.GetChild(i);
            var n = c.GetText();
            if (n == "(" || n == ")")
                continue;
            pred.Add(n);
        }
        var scope = (Scope) this.scopes.Peek();
        if (!neg) {
            scope.addatom(new Atom(pred));
        } else {
            scope.addnegatom(new Atom(pred));
        }
    }

    public override void EnterPrecondition(pddlParser.PreconditionContext ctx) {
        /*
        self.scopes.append(Scope())
        */
        this.scopes.Push( new Scope());
    }

    public override void ExitPrecondition(pddlParser.PreconditionContext ctx) {
        /*
        scope = self.scopes.pop()
        self.scopes[-1].precondition_pos = set( scope.atoms )
        self.scopes[-1].precondition_neg = set( scope.negatoms )
        */
        var scope = (Scope) this.scopes.Pop();
        var op = (Operator)this.scopes.Peek();
        op.precondition_pos = new HashSet<object>( scope.atoms );
        op.precondition_neg = new HashSet<object>( scope.negatoms );
    }

    public override void EnterEffect(pddlParser.EffectContext ctx) {
        /*
        self.scopes.append(Scope())
        */
        this.scopes.Push(new Scope());
    }

    public override void ExitEffect(pddlParser.EffectContext ctx) {
        /*
        scope = self.scopes.pop()
        self.scopes[-1].effect_pos = set( scope.atoms )
        self.scopes[-1].effect_neg = set( scope.negatoms )
        */
        var scope = (Scope) this.scopes.Pop();
        var op = (Operator)this.scopes.Peek();
        op.effect_pos = new HashSet<object>( scope.atoms );
        op.effect_neg = new HashSet<object>( scope.negatoms );
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
        var negscope = false;
        var nchilds = 5; // ctx.getChildCount();
        for (int i = 0; i < nchilds; i++) {
            var c = ctx.GetChild(i);
            if (c.GetText() == "not") {
                negscope = true;
                break;
            }
        }
        this.negativescopes.Push(negscope);
    }

    public override void ExitGoalDesc(pddlParser.GoalDescContext ctx) {
        /*
        self.negativescopes.pop()
        */
        this.negativescopes.Pop();
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
        var negscope = false;
        var nchilds = 5; // ctx.getChildCount();
        for (int i = 0; i < nchilds; i++) {
            var c = ctx.GetChild(i);
            if (c.GetText() == "not") {
                negscope = true;
                break;
            }
        }
        this.negativescopes.Push(negscope);
    }

    public override void ExitPEffect(pddlParser.PEffectContext ctx) {
        /*
        self.negativescopes.pop()
        */
        this.negativescopes.Pop();
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
        System.Console.WriteLine("-> tnam");
        foreach (var v in ctx.NAME()) {
            var vname = v.GetText();
            var op = (Operator)this.scopes.Peek();
            op.variable_list.Add(vname, null);
        }
        foreach (var vs in ctx.singleTypeNameList()) {
            var t = vs.r_type().GetText();
            foreach (var v in vs.NAME()) {
                var vname = v.GetText();
                var op = (Operator)this.scopes.Peek();
                op.variable_list.Add(vname, t);
            }
        }
    }

    public override void EnterConstantsDef(pddlParser.ConstantsDefContext ctx) {
        /*
        self.scopes.append(Obj())
        */
        this.scopes.Push(new Obj());
    }

    public override void ExitConstantsDef(pddlParser.ConstantsDefContext ctx) {
        /*
        scope = self.scopes.pop()
        self.objects = scope.variable_list
        */
        var scope = (Obj)this.scopes.Pop();
        this.objects = scope.variable_list;
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
        if (this.objects != null && this.objects.Count() > 0 && !this.typesdef) {
            var vs = new HashSet<string>();
            foreach (var opn in this.objects.Keys) {
                var oper = (Operator)this.objects[opn];
                var alls = new HashSet<object>();
                alls.UnionWith(oper.precondition_pos);
                alls.UnionWith(oper.precondition_neg);
                alls.UnionWith(oper.effect_pos);
                alls.UnionWith(oper.effect_neg);
                foreach (Atom a in alls) {
                    foreach (var s in a.predicate) {
                        if (!s.StartsWith("?")) {
                            vs.Add(s);
                        }
                    }
                }
            }
            this.objects = vs.ToDictionary(h => h, h => (object)null);
        }
    }

}

internal class ProblemListener : pddlBaseListener {
        /*
        self.objects = {}
        self.initialstate = []
        self.goals = []
        self.scopes = []
        */
    internal Dictionary<string, object> objects = new Dictionary<string, object>();
    internal HashSet<object> initialstate = new HashSet<object>();
    internal HashSet<object> goals = new HashSet<object>();
    Stack<IScopeItem> scopes = new Stack<IScopeItem>();

    public override void EnterInit(pddlParser.InitContext ctx) {
        /*
        self.scopes.append(Scope())
        */
        this.scopes.Push(new Scope());
    }

    public override void ExitInit(pddlParser.InitContext ctx) {
        /*
        self.initialstate = set( self.scopes.pop().atoms )
        */
        var scope = (Scope)this.scopes.Pop();
        this.initialstate = new HashSet<object>( scope.atoms );
    }

    public override void EnterGoal(pddlParser.GoalContext ctx) {
        /*
        self.scopes.append(Scope())
        */
        this.scopes.Push(new Scope());
    }

    public override void ExitGoal(pddlParser.GoalContext ctx) {
        /*
        self.goals = set( self.scopes.pop().atoms )
        */
        var scope = (Scope)this.scopes.Pop();
        this.goals = new HashSet<object>( scope.atoms );
    }

    public override void EnterAtomicNameFormula(pddlParser.AtomicNameFormulaContext ctx) {
        /*
        pred = []
        for c in ctx.getChildren():
            n = c.getText()
            if n == '(' or n == ')':
                continue
            pred.append(n)
        scope = self.scopes[-1]
        scope.addatom(Atom(pred))
        */

        System.Console.WriteLine("-> namf");
        var pred = new List<string>();
        var nchilds = 5 ; // TO DO. MAL OJO. va ctx.getChildCount()
        for (int i = 0; i < nchilds; i++) {
            var c = ctx.GetChild(i);
            var n = c.GetText();
            if (n == "(" || n == ")")
                continue;
            pred.Add(n);
        }
        var scope = (Scope) this.scopes.Peek();
        scope.addatom(new Atom(pred));
    }

    public override void EnterAtomicTermFormula(pddlParser.AtomicTermFormulaContext ctx) {
        /*
        # with a NOT!
        pred = []
        for c in ctx.getChildren():
            n = c.getText()
            if n == '(' or n == ')':
                continue
            pred.append(n)
        scope = self.scopes[-1]
        scope.addatom(Atom(pred))
        */
        System.Console.WriteLine("-> terf");
        var pred = new List<string>();
        var nchilds = 5 ; // TO DO. MAL OJO. va ctx.getChildCount()
        for (int i = 0; i < nchilds; i++) {
            var c = ctx.GetChild(i);
            var n = c.GetText();
            if (n == "(" || n == ")")
                continue;
            pred.Add(n);
        }
        var scope = (Scope) this.scopes.Peek();
        scope.addatom(new Atom(pred));
    }

    public override void EnterTypedNameList(pddlParser.TypedNameListContext ctx) {
        /*
        for v in ctx.NAME():
            vname = v.getText()
            self.scopes[-1].variable_list[v.getText()] = None
        for vs in ctx.singleTypeNameList():
            t = vs.r_type().getText()
            for v in vs.NAME():
                vname = v.getText()
                self.scopes[-1].variable_list[vname] = t
        */
        System.Console.WriteLine("-> tnam");
        foreach (var v in ctx.NAME()) {
            var vname = v.GetText();
            var op = (Operator)this.scopes.Peek();
            op.variable_list.Add(vname, null);
        }
        foreach (var vs in ctx.singleTypeNameList()) {
            var t = vs.r_type().GetText();
            foreach (var v in vs.NAME()) {
                var vname = v.GetText();
                var op = (Operator)this.scopes.Peek();
                op.variable_list.Add(vname, t);
            }
        }
    }

    public override void EnterObjectDecl(pddlParser.ObjectDeclContext ctx) {
        /*
        self.scopes.append(Obj())
        */
        this.scopes.Push(new Obj());
    }

    public override void ExitObjectDecl(pddlParser.ObjectDeclContext ctx) {
        /*
        scope = self.scopes.pop()
        self.objects = scope.variable_list
        */
        var scope = (Obj)this.scopes.Pop();
        this.objects = scope.variable_list;
    }

    public override void ExitProblem(pddlParser.ProblemContext ctx) {
        /*
        if not self.objects:
            vs = set()
            for a in self.initialstate:
                for s in a.predicate:
                    vs.add( (s, None) )
            for a in self.goals:
                for s in a.predicate:
                    vs.add( (s, None) )
            self.objects = dict( vs )
        */
        if (this.objects != null && this.objects.Count() > 0) {
            var vs = new HashSet<string>();
            foreach (Atom a in this.initialstate) {
                foreach (var s in a.predicate) {
                    vs.Add(s);
                }
            }
            foreach (Atom a in this.goals) {
                foreach (var s in a.predicate) {
                    vs.Add(s);
                }
            }
            this.objects = vs.ToDictionary(h => h, h => (object)null);
        }
    }

}

public class DomainProblem {

    private DomainListener domain;
    private ProblemListener problem;
    
    public DomainProblem() {
    }

    ///<summary>
    /// Returns an iterator of the names of the actions defined in
    /// the domain file.
    ///</summary>
    public IEnumerable<string> operators {
        get { return this.domain.operators.Keys; }
    }

    ///<summary>
    /// Returns a set of atoms (tuples of strings) corresponding to the intial
    /// state defined in the problem file.
    ///</summary>
    public ISet<object> initialstate {
        get { return this.problem.initialstate; }
    }

    ///<summary>
    /// Returns a set of atoms (tuples of strings) corresponding to the goals
    /// defined in the problem file.
    ///</summary>
    public ISet<object> goals {
        get { return this.problem.goals; }
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

