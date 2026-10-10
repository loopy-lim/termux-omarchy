package android.util;
/** HOST STUB */ public final class SparseArray<T> {private final java.util.Map<Integer,T> values=new java.util.HashMap<>();
 public T get(int key){return values.get(key);} public void put(int key,T value){values.put(key,value);}
 public void remove(int key){values.remove(key);} public void clear(){values.clear();}}
