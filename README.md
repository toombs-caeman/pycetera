# extremsim
http://blog.ezyang.com/2012/11/extremist-programming/
taking one idea to the max as a learning experiment.
* What if everything was generators?
* what if nothing was a generator (iterators only)?

# golf
the game where keystrokes == bad

# ideas
* allow f-string unpacking just like tuple unpacking
    - perhaps use regex syntax, assigning named groups only
    
* expand lens concept to handle map/filter/reduce
    
* how allow loop ordering for pure nested loops to be dynamically rewritten
    
* reversable functions `__rcall__`
# new functional syntax
to handle functions of one argument `o`
* map 
    * getattr `o.attr`
    * getitem `o[item]`
        * unpack on special value `slice(None, None, None)` `[:]`
        * filter on special type `type(self)`
    * call `o._(args)`
* sum type `|`
* filter `|...`
    * if map fails, then return the rhs
    * if rhs == ... and unpacking, then filter it out
    * if isinstance(rhs, Lens), execute the lens before returning
    * this implements sum types
* unpack `[:]`
    * map the tail call over each element
    * filter for each end element

```
X.bar(foo) # return foo.bar
X['bar'](foo) # return foo['bar']
X._('bar')(foo) # return foo('bar')
X[:].bar[3](foo) # return [i.bar[3] for i in foo]

X[:][X!=None].attr(foo) # return [i.attr for i in foo if i != None]
```
to handle functions of two arguments `x, y`
# rejected ideas
* symbolic math, see sympy
