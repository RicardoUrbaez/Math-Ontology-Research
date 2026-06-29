# 4.3 Kind/Role Classification

The project distinguishes kind concepts from role concepts because mathematical speech often depends on whether a symbol names an independent entity or a context-dependent function in an expression. Kind concepts are rigid mathematical entities, such as matrix, integer, derivative, point, or probability. Role concepts are anti-rigid and relational, such as variable, coefficient, operand, parameter, or exponent.

The Week 3 classifier assigns 487 concepts to `kind` and 13 concepts to `role` across the 500 target concepts. The classifier begins with the Week 2 validation-set type when available, then applies lexical rules for role-bearing terms such as coefficient, variable, operand, parameter, argument, and index. All other concepts default to kind unless a rule explicitly marks them as roles.

This conservative rule is useful for accessibility because a role term usually needs extra context in speech. For example, coefficient should be spoken as a factor multiplying another term, while matrix can be spoken as an independent linear-algebra object. The distinction also supports SPARQL retrieval: users can ask for all role-bearing concepts, all kind concepts in a domain, or all concepts whose meaning changes with document context.

The semantic-type distribution used for gloss generation is: function: 12, matrix: 14, operator: 32, relation: 8, scalar: 395, set: 6, transformation: 26, vector: 7. These semantic types drive the eight template families used by the gloss dictionary.
