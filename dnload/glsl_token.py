from dnload.common import is_listing
from dnload.glsl_access import is_glsl_access
from dnload.glsl_name import is_glsl_name
from dnload.glsl_operator import is_glsl_operator
from dnload.glsl_paren import is_glsl_paren
from dnload.glsl_type import is_glsl_type

########################################
# GlslToken ############################
########################################

class GlslToken:
  """Holds single instance of a GLSL token. Actually more of a token container."""

  def __init__(self, token):
    """Constructor."""
    self.__parent = None
    self.__left = []
    self.__middle = []
    self.__right = []
    # Prevent degeneration, collapse tokens with only single middle element.
    if is_glsl_token(token):
      single = token.getSingleChild()
      if is_glsl_token(single):
        single.setParent(None)
      elif is_listing(single):
        for ii in single:
          if not is_glsl_token(ii):
            raise RuntimeError("non-token '%s' acquired from getSingleChild on '%s'" % (str(single), str(self)))
          ii.setParent(None)
      self.addMiddle(single)
    else:
      self.addMiddle(token)

  def addLeft(self, op):
    """Add left child token."""
    # List case.
    if is_listing(op):
      for ii in op:
        self.addleft(ii)
      return
    # Single case.
    self.__left += [op]
    op.setParent(self)

  def addMiddle(self, op):
    """Add middle child token."""
    # List case.
    if is_listing(op):
      for ii in op:
        self.addMiddle(ii)
      return
    # Tokens added normally.
    if is_glsl_token(op):
      self.__middle += [op]
      op.setParent(self)
    # Non-tokens added as-is.
    else:
      self.__middle += [op]

  def addRight(self, op):
    """Add right child token."""
    # List case.
    if is_listing(op):
      for ii in op:
        self.addRight(ii)
      return
    # Single case.
    self.__right += [op]
    op.setParent(self)

  def flatten(self):
    """Flatten this token into a list."""
    ret = []
    # Left
    for ii in self.__left:
      ret += ii.flatten()
    # Middle may be a token or a listing in itself.
    for ii in self.__middle:
      if is_glsl_token(ii):
        ret += ii.flatten()
      else:
        ret += [ii]
    # Right.
    for ii in self.__right:
      ret += ii.flatten()
    return ret

  def flattenString(self):
    """Flatten this token into a string."""
    ret = ""
    tokens = self.flatten()
    for ii in tokens:
      ret += ii.format(False)
    return ret

  def getSingleChild(self):
    """Degeneration preventation. If token only has a single child, return that instead."""
    lr = len(self.__left) + len(self.__right)
    # If left and right exist, default option is to return node itself.
    if 0 < lr:
      if not self.__middle:
        raise RuntimeError("cannot have left or right without middle")
      return self
    # If left and right did not exist, return middle.
    elif self.__middle:
      if is_listing(self.__middle):
        if 1 >= len(self.__middle):
          return self.__middle[0]
      return self.__middle
    # Should never happen.
    raise RuntimeError("token has no content")

  def removeChild(self, op):
    """Remove a child from this."""
    for ii in range(len(self.__left)):
      vv = self.__left[ii]
      if vv == op:
        self.__left.pop(ii)
        return
    for ii in range(len(self.__right)):
      vv = self.__right[ii]
      if vv == op:
        self.__right.pop(ii)
        return
    for ii in range(len(self.__middle)):
      vv = self.__middle[ii]
      if vv == op:
        self.__middle.pop(ii)
        return
    raise RuntimeError("could not remove child '%s' from '%s'" % (str(op), str(self)))

  def removeFromParent(self):
    """Remove this from its parent."""
    self.__parent.removeChild(self)
    self.__parent = None

  def setParent(self, op):
    """Set parent."""
    if op and self.__parent and (self.__parent != op):
      raise RuntimeError("hierarchy inconsistency in '%s', parent '%s' over existing '%s'" %
          (str(self), str(op), str(self.__parent)))
    self.__parent = op

  def simplify(self):
    """Perform any simple simplification and stop."""
    return False
    # Trivial case, single-element expression surrounded by parens.
    if (len(self.__left) == 1) and (len(self.__right) == 1):
      left = self.__left[0].flattenString()
      right = self.__right[0].flattenString()
      if ("(" == left) and (")" == right):
        if 1 == len(self.__middle):
          self.__left[0].removeFromParent()
          self.__right[0].removeFromParent()
          self.__left = []
          self.__right = []
          return True
    for ii in self.__left:
      if ii.simplify():
        return True
    for ii in self.__right:
      if ii.simplify():
        return True
    for ii in self.__middle:
      if is_glsl_token(ii):
        if ii.simplify():
          return True
    return False

  def __str__(self):
    """String representation."""
    if 1 == len(self.__middle):
      return "Token(%i:'%s':%i)" % (len(self.__left), str(self.__middle[0]), len(self.__right))
    return "Token(%i:%i:%i)" % (len(self.__left), len(self.__middle), len(self.__right))

########################################
# Functions ############################
########################################

def get_single_token(op):
  """Return single token element from given list, if possible."""
  if is_glsl_token(op):
    return op.getSingleChild()
  return None

def is_glsl_token(op):
  """Tell if given object is a GLSL token."""
  return isinstance(op, GlslToken)

def token_list_create(lst):
  """Build a token list from a given listing, ensuring every element is a token."""
  ret = []
  for ii in lst:
    if not is_glsl_token(ii):
      ret += [GlslToken(ii)]
    elif ii:
      ret += [ii]
  return ret

def token_tree_build(lst):
  """Builds and balances a token tree from given list."""
  # Ensure all list elements are tokens.
  lst = token_list_create(lst)
  # Might be that everything is lost at this point.
  if not lst:
    return None
  # Start iteration over tokenized list.
  bracket_count = 0
  paren_count = 0
  first_bracket_index = -1
  first_paren_index = -1
  highest_operator = None
  highest_operator_index = -1
  print("building token tree from: %s" % (str(map(str, lst))))
  for ii in range(len(lst)):
    vv = lst[ii].getSingleChild()
    if is_glsl_paren(vv):
      # Bracket case.
      if vv.isBracket():
        new_bracket_count = vv.updateBracket(bracket_count)
        if new_bracket_count == bracket_count:
          raise RuntimeError("wut?")
        bracket_count = new_bracket_count
        # Return split on bracket.
        if 0 >= bracket_count:
          if 0 > first_bracket_index:
            raise RuntimeError("bracket inconsistency")
          middle = GlslToken(token_tree_build(lst[first_bracket_index + 1 : ii]))
          right = GlslToken(lst[ii])
          # Read types, names or accesses left.
          left = [GlslToken(lst[first_bracket_index])]
          iter_left = first_bracket_index - 1
          while iter_left > 0:
            prospect = lst[iter_left]
            if is_glsl_access(prospect) or is_glsl_name(prospect) or is_glsl_type(prospect):
              left = [prospect] + left
              iter_left -= 1
            else:
              break
          # Create split.
          left = GlslToken(lst[first_bracket_index])
          ret = GlslToken(middle)
          ret.addLeft(left)
          ret.addRight(right)
          return token_tree_build(lst[:first_bracket_index] + [ret] + lst[ii + 1:])
        elif (1 == bracket_count) and (0 > first_bracket_index):
          first_bracket_index = ii
      # Paren case.
      elif vv.isParen():
        new_paren_count = vv.updateParen(paren_count)
        if new_paren_count == paren_count:
          raise RuntimeError("wut?")
        paren_count = new_paren_count
        # Return split on paren.
        if 0 >= paren_count:
          if 0 > first_paren_index:
            raise RuntimeError("paren inconsistency")
          # It's ok to have empty parens, as opposed to empty brackets.
          middle = token_tree_build(lst[first_paren_index + 1 : ii])
          print("trying '%s'" % str(middle))
          if middle:
            print(str(middle))
            middle = GlslToken(middle)
          else:
            middle = None
          right = GlslToken(lst[ii])
          # Read types, names or accesses left.
          left = [GlslToken(lst[first_paren_index])]
          iter_left = first_paren_index - 1
          while iter_left >= 0:
            prospect = lst[iter_left]
            if is_glsl_access(prospect) or is_glsl_name(prospect) or is_glsl_type(prospect):
              left = [prospect] + left
              iter_left -= 1
            else:
              break
          # Create split.
          left = GlslToken(left)
          ret = GlslToken(middle)
          ret.addLeft(left)
          ret.addRight(right)
          return token_tree_build(lst[:first_paren_index] + [ret] + lst[ii + 1:])
        elif (1 == paren_count) and (0 > first_paren_index):
          first_paren_index = ii
      # Curly braces impossible.
      else:
        raise RuntimeError("unknown paren object '%s'" % (str(vv)))
    if is_glsl_operator(vv):
      if (not highest_operator) or (highest_operator < vv):
        highest_operator = vv
        highest_operator_index = ii
  # Iteration done. Collect the pieces.
  if highest_operator:
    left = token_tree_build(lst[:highest_operator_index])
    right = token_tree_build(lst[highest_operator_index + 1:])
    ret = GlslToken(highest_operator)
    # Left must exist as long as the operator is not unary minus.
    if left:
      ret.addLeft(left)
    elif highest_operator != "-":
      raise RuntimeError("left component nonexistent for operator '%s'" % (str(highest_operator)))
    # Right must exist, there are no unary right operators in GLSL.
    ret.addRight(right)
    return ret
  # Only option at this point is that the list has no operators and no parens - return as itself.
  return GlslToken(lst)

def token_tree_simplify(op):
  """Perform first found simplify operation for given tree."""
  if op.simplify():
    return True
  return False