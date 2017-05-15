
/*
 * Copyright 2015 Hernán M. Foffani
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */

using System.Collections.Generic;
using System.IO;
using System.Linq;

using Antlr4.Runtime;

[assembly: System.CLSCompliant(true)]

namespace PDDLNET {

/// <summary>
/// Represents a strongly-typed, read-only collection of elements.
/// </summary>
/// <typeparam name="T">The type of the elements.
/// This type parameter is covariant. That is, you can use either the
/// type you specified or any type that is more derived.</typeparam>
/// <remarks>
/// IReadOnlyCollection is BUILTIN IN 4.5
/// </remarks>
public interface IROCollection<out T> : IEnumerable<T>, System.Collections.IEnumerable {
    /// <summary>
    /// Gets the number of elements in the collection.
    /// </summary>
    int Count { get; }
}


class HashFunctions {

    static object sync = new object();
    static int[] aes = null;
    static HashFunctions _provider = null;

    public int Universal<T>(T[] x) {
        if (x.Length == 0)
            return 0;
        var h = x[0].GetHashCode();
        var p = (1 << 61) - 1;
        for (int i = 1; i < x.Length; i++)
            h = ((h * aes[i % 100]) + x[i].GetHashCode()) % p;
        return h;
    }

    public static HashFunctions Provider {
        get {
            lock (sync) {
                if (HashFunctions._provider == null) {
                    HashFunctions._provider = new HashFunctions();
                }
                return HashFunctions._provider;
            }
        }
    }

    private HashFunctions() {
        if (aes == null) {
            aes = new int[100];
            var rnd = new System.Random();
            for (int i = 0; i < 100; i++) {
                aes[i] = 0;
                do {
                    aes[i] = rnd.Next();
                } while (aes[i] == 0 || aes[i] % 2 == 0);
            }
        }
    }

}

/// <summary>
/// Implements a strongly-typed, read-only collection of elements.
/// </summary>
/// <typeparam name="T">The type of the elements.
/// This type parameter is covariant. That is, you can use either the
/// type you specified or any type that is more derived.</typeparam>
public class ROCollection<T> : IROCollection<T> {

    private T[] _internalArray = new T[0];
    int _hash = 0;

    /// <summary>
    /// Constructor.
    /// </summary>
    public ROCollection() { }

    /// <summary>
    /// Constructor and factory.
    /// </summary>
    /// <param name="collection">The source of elements for this instance.</param>
    public ROCollection(IEnumerable<T> collection) {
        _internalArray = collection.ToArray();
        _hash = HashFunctions.Provider.Universal<T>(_internalArray);
    }

    /// <summary>
    /// Gets the number of elements in the collection.
    /// </summary>
    public int Count {
        get { return _internalArray.Length; }
    }

    /// <summary>
    /// Returns an enumerator that iterates through the collection.
    /// </summary>
    /// <returns>An enumerator that can be used to iterate through the collection.</returns>
    public IEnumerator<T> GetEnumerator() {
        return _internalArray.AsEnumerable().GetEnumerator();
    }

    System.Collections.IEnumerator System.Collections.IEnumerable.GetEnumerator() {
        return _internalArray.GetEnumerator();
    }

    /// <summary>
    /// Determines whether the specified object is equal to the current object.
    /// </summary>
    /// <param name="other">The object to compare with the current object.</param>
    /// <returns><c>true</c> if the specified object is equal to the current object; otherwise, <c>false</c>.</returns>
    public bool Equals(ROCollection<T> other) {
        if ((object)other == null)
            return false;
        return this.GetHashCode() == other.GetHashCode();
    }

    /// <summary>
    /// Serves as the default hash function.
    /// </summary>
    /// <returns>A hash code for the current object.</returns>
    public override int GetHashCode() {
        return _hash;
    }

    /// <summary>
    /// Determines whether the specified object is equal to the current object.
    /// </summary>
    /// <param name="obj">The object to compare with the current object.</param>
    /// <returns><c>true</c> if the specified object is equal to the current object; otherwise, <c>false</c>.</returns>
    public override bool Equals(object obj) {
        return this.Equals(obj as ROCollection<T>);
    }

    /// <summary>
    /// Determines whether two objects are equal.
    /// </summary>
    /// <param name="a">The first object.</param>
    /// <param name="b">The second object</param>
    /// <returns><c>true</c> if the both object are equal; otherwise, <c>false</c>.</returns>
    public static bool operator ==(ROCollection<T> a, ROCollection<T> b) {
        if (System.Object.ReferenceEquals(a, b)) {
            return true;
        }
        // null,null have already been considered in the previous if.
        if ((object)a == null) {
            return false;
        }
        return a.Equals(b);
    }

    /// <summary>
    /// Determines whether two objects are different.
    /// </summary>
    /// <param name="a">The first object.</param>
    /// <param name="b">The second object</param>
    /// <returns><c>true</c> if the both object are different; otherwise, <c>false</c>.</returns>
    public static bool operator !=(ROCollection<T> a, ROCollection<T> b) {
        return !(a == b);
    }

    /// <summary>
    /// Returns a string that represents the current object.
    /// </summary>
    /// <returns>A string that represents the current object.</returns>
    public override string ToString() {
        var s = new System.Text.StringBuilder();
        s.Append("(");
        foreach (var it in this._internalArray) {
            s.Append(it.ToString());
            s.Append(", ");
        }
        s.Append(")");
        return s.ToString();
    }
}


interface IScopeItem {
}

internal class Scope : IScopeItem {
    public List<ROCollection<string>> atoms = new List<ROCollection<string>>();
    public List<ROCollection<string>> negatoms = new List<ROCollection<string>>();

    public void addatom(IList<string> atompredicate) {
        atoms.Add(new ROCollection<string>(atompredicate));
    }

    public void addnegatom(IList<string> atompredicate) {
        negatoms.Add(new ROCollection<string>(atompredicate));
    }
}

internal class Obj : IScopeItem {
    public Dictionary<string, string> variable_list = new Dictionary<string, string>();
}

public class Operator : IScopeItem {
    public string operator_name = "";
    public HashSet<ROCollection<string>> precondition_pos = null;
    public HashSet<ROCollection<string>> precondition_neg = null;
    public HashSet<ROCollection<string>> effect_pos = null;
    public HashSet<ROCollection<string>> effect_neg = null;
    public Dictionary<string, string> variable_list = new Dictionary<string, string>();

    public Operator(string name) {
        this.operator_name = name;
    }
}

internal class DomainListener : pddlBaseListener {
    internal Dictionary<string, string> objects = new Dictionary<string, string>();
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
        // System.Console.WriteLine("-> tvar");
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
        // System.Console.WriteLine("-> terf");
        var neg = this.negativescopes.Peek();
        var pred = new List<string>();
        for (int i = 0; i < ctx.ChildCount; i++) {
            var c = ctx.GetChild(i);
            var n = c.GetText();
            if (n == "(" || n == ")")
                continue;
            pred.Add(n);
        }
        var scope = (Scope) this.scopes.Peek();
        if (!neg) {
            scope.addatom(pred);
        } else {
            scope.addnegatom(pred);
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
        op.precondition_pos = new HashSet<ROCollection<string>>( scope.atoms );
        op.precondition_neg = new HashSet<ROCollection<string>>( scope.negatoms );
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
        op.effect_pos = new HashSet<ROCollection<string>>( scope.atoms );
        op.effect_neg = new HashSet<ROCollection<string>>( scope.negatoms );
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
        for (int i = 0; i < ctx.ChildCount; i++) {
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
        for (int i = 0; i < ctx.ChildCount; i++) {
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
        for v in ctx.name():
            vname = v.getText()
            self.scopes[-1].variable_list[v.getText()] = None
        for vs in ctx.singleTypeNameList():
            t = vs.r_type().getText()
            for v in vs.name():
                vname = v.getText()
                self.scopes[-1].variable_list[vname] = t
        */
        // System.Console.WriteLine("-> tnam");
        foreach (var v in ctx.name()) {
            var vname = v.GetText();
            var op = (Operator)this.scopes.Peek();
            op.variable_list.Add(vname, null);
        }
        foreach (var vs in ctx.singleTypeNameList()) {
            var t = vs.r_type().GetText();
            foreach (var v in vs.name()) {
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
        if (this.objects.Count() == 0 && !this.typesdef) {
            var vs = new HashSet<string>();
            foreach (var opn in this.operators.Keys) {
                var oper = (Operator)this.operators[opn];
                var alls = new HashSet<ROCollection<string>>();
                alls.UnionWith(oper.precondition_pos);
                alls.UnionWith(oper.precondition_neg);
                alls.UnionWith(oper.effect_pos);
                alls.UnionWith(oper.effect_neg);
                foreach (ROCollection<string> atom in alls) {
                    foreach (var vname in atom) {
                        if (!vname.StartsWith("?")) {
                            vs.Add(vname);
                        }
                    }
                }
            }
            this.objects = vs.ToDictionary(h => h, h => (string)null);
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
    internal Dictionary<string, string> objects = new Dictionary<string, string>();
    internal HashSet<ROCollection<string>> initialstate =
        new HashSet<ROCollection<string>>();
    internal HashSet<ROCollection<string>> goals =
        new HashSet<ROCollection<string>>();
    Stack<IScopeItem> scopes = new Stack<IScopeItem>();

    public override void EnterInit(pddlParser.InitContext ctx) {
        /*
        self.scopes.append(Scope())
        */
        // System.Console.WriteLine("-> ini");
        this.scopes.Push(new Scope());
    }

    public override void ExitInit(pddlParser.InitContext ctx) {
        /*
        self.initialstate = set( self.scopes.pop().atoms )
        */
        // System.Console.WriteLine("<- ini");
        var scope = (Scope)this.scopes.Pop();
        this.initialstate = new HashSet<ROCollection<string>>( scope.atoms);
    }

    public override void EnterGoal(pddlParser.GoalContext ctx) {
        /*
        self.scopes.append(Scope())
        */
        // System.Console.WriteLine("-> goal");
        this.scopes.Push(new Scope());
    }

    public override void ExitGoal(pddlParser.GoalContext ctx) {
        /*
        self.goals = set( self.scopes.pop().atoms )
        */
        // System.Console.WriteLine("<- goal");
        var scope = (Scope)this.scopes.Pop();
        this.goals = new HashSet<ROCollection<string>>( scope.atoms);
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
        // System.Console.WriteLine("-> namf");
        var pred = new List<string>();
        for (int i = 0; i < ctx.ChildCount; i++) {
            var c = ctx.GetChild(i);
            var n = c.GetText();
            if (n == "(" || n == ")")
                continue;
            pred.Add(n);
        }
        var scope = (Scope) this.scopes.Peek();
        scope.addatom(pred);
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
        // System.Console.WriteLine("-> terf");
        var pred = new List<string>();
        for (int i = 0; i < ctx.ChildCount; i++) {
            var c = ctx.GetChild(i);
            var n = c.GetText();
            if (n == "(" || n == ")")
                continue;
            pred.Add(n);
        }
        var scope = (Scope) this.scopes.Peek();
        scope.addatom(pred);
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
        // System.Console.WriteLine("-> tnam");
        foreach (var v in ctx.name()) {
            var vname = v.GetText();
            var op = (Operator)this.scopes.Peek();
            op.variable_list.Add(vname, null);
        }
        foreach (var vs in ctx.singleTypeNameList()) {
            var t = vs.r_type().GetText();
            foreach (var v in vs.name()) {
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
        if (this.objects.Count() == 0) {
            var vs = new HashSet<string>();
            foreach (var a in this.initialstate) {
                foreach (var s in a) {
                    vs.Add(s);
                }
            }
            foreach (var a in this.goals) {
                foreach (var s in a) {
                    vs.Add(s);
                }
            }
            this.objects = vs.ToDictionary(h => h, h => (string)null);
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
    public ISet<ROCollection<string>> initialstate {
        get { return this.problem.initialstate; }
    }

    ///<summary>
    /// Returns a set of atoms (tuples of strings) corresponding to the goals
    /// defined in the problem file.
    ///</summary>
    public ISet<ROCollection<string>> goals {
        get { return this.problem.goals; }
    }

    ///<summary>
    /// Returns a dictionary of key value pairs where the key is the name of
    /// an object and the value is it's type (None in case is untyped.)
    ///</summary>
    public IDictionary<string, string> worldobjects {
        get {
            return this.domain.objects
                .Concat(this.problem.objects
                    .Where(kvp => !this.domain.objects.ContainsKey(kvp.Key)))
                .ToDictionary(kvp => kvp.Key, kvp => kvp.Value);
        }
    }

    ///<summary>
    /// Constructor.
    ///</summary>
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

    /*
     * ground
     *
     */

    public Operator get_operator(string op_name) {
        return (Operator) this.domain.operators[op_name];
    }

    public IEnumerable<Operator> ground_operator(string op_name) {
        var op = (Operator)this.domain.operators[op_name];
        set_operator_groundspace(op_name, op.variable_list);
        foreach (var groundvars in this.instantiate(op_name)) {
            var st = groundvars.ToDictionary(kvp=>kvp.Key, kvp=>kvp.Value);
            var gop = new Operator(op_name);
            gop.variable_list = st;
            gop.precondition_pos = ground(op.precondition_pos, st);
            gop.precondition_neg = ground(op.precondition_neg, st);
            gop.effect_pos = ground(op.effect_pos, st);
            gop.effect_neg = ground(op.effect_neg, st);
            yield return gop;
        }
    }

    public string to_string(HashSet<ROCollection<string>> set) {
        var sb = new System.Text.StringBuilder();
        sb.Append("{ ");
        foreach (var p in set) {
            sb.Append(p.ToString());
            sb.Append("; ");
        }
        sb.Append("}");
        return sb.ToString();
    }

    private HashSet<ROCollection<string>> ground(
        HashSet<ROCollection<string>> predvars,
        Dictionary<string, string> varvals) {
    /*
     *     g = [ varvals[v] if v in varvals else v for v in self.predicate ]
     *     return tuple(g)
     *  set( [ a.ground( st ) for a in op.precondition_pos ] )
     *
     */
        var r = new List<ROCollection<string>>();
        foreach (var p in predvars) {
            var l = new List<string>();
            foreach (var v in p) {
                 l.Add( varvals.ContainsKey(v) ? varvals[v] : v);
            }
            var pg = new ROCollection<string>(l);
            r.Add( pg);
        }
        return new HashSet<ROCollection<string>>(r);
    }

    private IEnumerable<string> typesymbols(string t) {
        // return ( k for k,v in self.worldobjects().items() if v == t )
        return this.worldobjects
            .Where(kvp => kvp.Value == t)
            .Select(kvp => kvp.Key);
    }

    Dictionary<string,Dictionary<string,List<string>>> vargroundspace =
        new Dictionary<string,Dictionary<string,List<string>>>();

    private void set_operator_groundspace(string opname,
                    IDictionary<string, string> variables) {
        /*
         *  def _set_operator_groundspace(self, opname, variables):
         *      # cache the variables ground space for each operator.
         *      if opname not in self.vargroundspace:
         *          d = self.vargroundspace.setdefault(opname, {})
         *          for vname, t in variables:
         *              for symb in self._typesymbols(t):
         *                  d.setdefault(vname, []).append(symb)
         */
        if (!this.vargroundspace.ContainsKey(opname)) {
            // this.vargroundspace.Add(opname, new Dictionary<string, List<string>>());
            var d = this.vargroundspace[opname] = new Dictionary<string, List<string>>();
            foreach (var kvp in variables) {
                var varname = kvp.Key;
                d[varname] = new List<string>();
                foreach (var symb in this.typesymbols(kvp.Value)) {
                    d[varname].Add( symb);
                }
            }
        }
    }

    private IEnumerable<IEnumerable<KeyValuePair<string,string>>> instantiate(string opname) {
        /*
         * d = self.vargroundspace[opname]
         * # expands the dict to something like:
         * #[ [('?x1','A'),('?x1','B')..], [('?x2','M'),('?x2','N')..],..]
         * expanded = [ [ (vname, symb) for symb in d[vname] ] for vname in d ]
         * # cartesian product.
         * return itertools.product(*expanded)
         */
        //var expanded = List<List<KeyValuePair<string,string>>>();
        var d = this.vargroundspace[opname];
        var expanded = new List<List<KeyValuePair<string,string>>>();
        foreach (var vname in d.Keys) {
            var p = new List<KeyValuePair<string,string>>();
            foreach (var s in d[vname]) {
                p.Add(new KeyValuePair<string,string>(vname, s));
            }
            expanded.Add(p);
        }
        var cp = CartesianProduct<KeyValuePair<string,string>>( expanded);
        return cp;
    }


    public static IEnumerable<IEnumerable<T>> CartesianProduct<T>(
        IEnumerable<IEnumerable<T>> inputs) {

        return inputs.Aggregate(
            Return(Enumerable.Empty<T>()),
                (soFar, input) =>
                    from prevProductItem in soFar
                    from item in input
                    select prevProductItem.Append(item));
    }
    private static IEnumerable<T> Return<T>(T item) {
        return new T[] { item };
    }

/*
    public static IEnumerable<IEnumerable<T>> CartesianProduct<T>(
        IEnumerable<IEnumerable<T>> inputs) {

        return inputs.Aggregate(
            (IEnumerable<IEnumerable<T>>) new T[][] { new T[0] },
            (soFar, input) =>
                from prevProductItem in soFar
                from item in input
                select prevProductItem.Concat(new T[] { item }));
    }

    public static IEnumerable<IEnumerable<T>> CartesianProduct<T>(
        params IEnumerable<T>[] inputs) {

        IEnumerable<IEnumerable<T>> e = inputs;
        return CartesianProduct(e);
    }
*/

}

static class AppendExtension {
    public static IEnumerable<T> Append<T>(this IEnumerable<T> that, T item) {
        IEnumerable<T> itemAsSequence = new T[] { item };
        return that.Concat(itemAsSequence);
    }
}

}

